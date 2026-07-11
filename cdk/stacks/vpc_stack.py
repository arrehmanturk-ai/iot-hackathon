from aws_cdk import Stack, aws_ec2 as ec2
from constructs import Construct


class VpcStack(Stack):
    """
    VPC with:
      - public subnets  -> Bastion Host lives here
      - private subnets (with NAT egress) -> MSK, Postgres EC2, Lambda live here
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self, "IotVpc",
            vpc_name="iot-hackathon-vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )
