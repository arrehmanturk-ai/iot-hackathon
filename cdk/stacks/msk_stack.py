from aws_cdk import Stack, aws_msk as msk, aws_ec2 as ec2, CfnOutput
from constructs import Construct


class MskStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.security_group = ec2.SecurityGroup(
            self, "MskSecurityGroup",
            vpc=vpc,
            description="Security group for MSK cluster + Kafka Connect",
            allow_all_outbound=True,
        )
        # Kafka broker + Zookeeper ports, open within the SG itself
        self.security_group.add_ingress_rule(
            self.security_group, ec2.Port.tcp_range(9092, 9098), "Kafka broker traffic"
        )
        self.security_group.add_ingress_rule(
            self.security_group, ec2.Port.tcp_range(2181, 2182), "Zookeeper traffic"
        )

        private_subnet_ids = [s.subnet_id for s in vpc.private_subnets]

        self.cluster = msk.CfnCluster(
            self, "IotMskCluster",
            cluster_name="iot-msk-cluster",
            kafka_version="3.6.0",
            number_of_broker_nodes=len(private_subnet_ids),  # one broker per AZ, min 2
            broker_node_group_info=msk.CfnCluster.BrokerNodeGroupInfoProperty(
                instance_type="kafka.t3.small",
                client_subnets=private_subnet_ids,
                security_groups=[self.security_group.security_group_id],
                storage_info=msk.CfnCluster.StorageInfoProperty(
                    ebs_storage_info=msk.CfnCluster.EBSStorageInfoProperty(volume_size=20)
                ),
            ),
            encryption_info=msk.CfnCluster.EncryptionInfoProperty(
                encryption_in_transit=msk.CfnCluster.EncryptionInTransitProperty(
                    client_broker="TLS_PLAINTEXT",
                    in_cluster=True,
                )
            ),
        )

        CfnOutput(self, "MskClusterArn", value=self.cluster.attr_arn)
