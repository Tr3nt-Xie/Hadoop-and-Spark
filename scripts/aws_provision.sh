#!/usr/bin/env bash
# Create the two Lab 4 nodes in your own AWS account and write .local/cluster.json.
#   AWS_PROFILE=lab4 bash scripts/aws_provision.sh          # create
#   AWS_PROFILE=lab4 bash scripts/aws_provision.sh stop     # stop both (keeps disks)
#   AWS_PROFILE=lab4 bash scripts/aws_provision.sh start    # start again, refresh IPs
#   AWS_PROFILE=lab4 bash scripts/aws_provision.sh destroy  # terminate, delete SG and key
#
# Two Ubuntu 22.04 x86_64 t3.medium (2 vCPU, 4 GiB, same class as the t2.medium
# in the handout) with Unlimited CPU credits so long runs are not throttled,
# 30 GB gp3 each, one security group: SSH from this machine's IP only, all
# traffic between the two nodes. Everything is tagged Project=ee542-lab4.
set -euo pipefail
cd "$(dirname "$0")/.."
REGION=${AWS_REGION:-us-west-2}; TYPE=${TYPE:-t3.medium}; KEY=lab4-key; SG=lab4-sg
PEM=$HOME/.ssh/$KEY.pem; TAG="Key=Project,Value=ee542-lab4"
A(){ aws --region "$REGION" "$@"; }
mkdir -p .local

ids(){ A ec2 describe-instances --filters "Name=tag:Project,Values=ee542-lab4" \
         "Name=instance-state-name,Values=pending,running,stopping,stopped" \
         --query 'Reservations[].Instances[].InstanceId' --output text; }

write_config(){
  local m w
  m=$(A ec2 describe-instances --filters "Name=tag:Name,Values=lab4-master" "Name=instance-state-name,Values=running" \
        --query 'Reservations[0].Instances[0].[PublicIpAddress,PrivateIpAddress,InstanceId]' --output text)
  w=$(A ec2 describe-instances --filters "Name=tag:Name,Values=lab4-worker" "Name=instance-state-name,Values=running" \
        --query 'Reservations[0].Instances[0].[PublicIpAddress,PrivateIpAddress,InstanceId]' --output text)
  read MP MI MID <<<"$m"; read WP WI WID <<<"$w"
  cat > .local/cluster.json <<JSON
{
  "region": "$REGION",
  "key_path": "$PEM",
  "known_hosts": ".local/known_hosts",
  "master": {"public_ip": "$MP", "private_ip": "$MI", "instance_id": "$MID"},
  "worker": {"public_ip": "$WP", "private_ip": "$WI", "instance_id": "$WID"}
}
JSON
  echo "master $MP ($MI)  worker $WP ($WI)"
  : > .local/known_hosts
  for ip in $MP $WP; do
    for i in $(seq 1 30); do ssh-keyscan -T 5 -t ed25519 "$ip" 2>/dev/null >> .local/known_hosts && break; sleep 5; done
  done
  echo "host keys recorded:"; ssh-keygen -lf .local/known_hosts
}

case "${1:-create}" in
create)
  [ -z "$(ids)" ] || { echo "Lab 4 instances already exist: $(ids)"; exit 1; }
  AMI=$(A ssm get-parameter --name /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id \
          --query Parameter.Value --output text)
  VPC=$(A ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
  SUBNET=$(A ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=default-for-az,Values=true \
             --query 'Subnets[0].SubnetId' --output text)
  MYIP=$(curl -s https://checkip.amazonaws.com)/32
  echo "AMI $AMI  VPC $VPC  subnet $SUBNET  SSH allowed from $MYIP"
  if [ ! -f "$PEM" ]; then
    A ec2 create-key-pair --key-name $KEY --key-type ed25519 --tag-specifications "ResourceType=key-pair,Tags=[{$TAG}]" \
      --query KeyMaterial --output text > "$PEM"
    chmod 600 "$PEM"
  fi
  SGID=$(A ec2 create-security-group --group-name $SG --description "EE542 Lab 4 Hadoop/Spark" --vpc-id $VPC \
           --tag-specifications "ResourceType=security-group,Tags=[{$TAG}]" --query GroupId --output text)
  A ec2 authorize-security-group-ingress --group-id $SGID --protocol tcp --port 22 --cidr $MYIP >/dev/null
  A ec2 authorize-security-group-ingress --group-id $SGID --protocol -1 --source-group $SGID >/dev/null
  for NAME in lab4-master lab4-worker; do
    A ec2 run-instances --image-id $AMI --instance-type $TYPE --key-name $KEY --subnet-id $SUBNET \
      --security-group-ids $SGID --associate-public-ip-address --credit-specification CpuCredits=unlimited \
      --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=30,VolumeType=gp3,DeleteOnTermination=true}' \
      --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{$TAG}]" \
      --query 'Instances[0].InstanceId' --output text
  done
  A ec2 wait instance-running --instance-ids $(ids)
  write_config ;;
stop)    A ec2 stop-instances --instance-ids $(ids) --query 'StoppingInstances[].CurrentState.Name' --output text ;;
start)   A ec2 start-instances --instance-ids $(ids) >/dev/null; A ec2 wait instance-running --instance-ids $(ids); write_config ;;
destroy)
  I=$(ids); [ -n "$I" ] && { A ec2 terminate-instances --instance-ids $I >/dev/null; A ec2 wait instance-terminated --instance-ids $I; }
  SGID=$(A ec2 describe-security-groups --filters Name=group-name,Values=$SG --query 'SecurityGroups[0].GroupId' --output text)
  [ "$SGID" != None ] && A ec2 delete-security-group --group-id $SGID
  A ec2 delete-key-pair --key-name $KEY; rm -f "$PEM"; echo destroyed ;;
*) echo "usage: $0 [create|stop|start|destroy]"; exit 1 ;;
esac
