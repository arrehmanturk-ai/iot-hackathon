import os
from aws_cdk import (
    Stack, CfnOutput, Duration,
    aws_ec2 as ec2,
    aws_lambda as _lambda,
    aws_iam as iam,
)
from constructs import Construct

LAYER_ZIP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lambda", "layer", "kafka-python-layer.zip"
)


class BridgeLambdaStack(Stack):
    """
    Lambda that AWS IoT Core Rules invoke to forward simulator messages into MSK's
    'iot-events' topic. Runs inside the VPC private subnets so it can reach MSK.
    """

    def __init__(
        self, scope: Construct, construct_id: str,
        vpc: ec2.Vpc, msk_cluster_arn: str, msk_security_group: ec2.SecurityGroup, **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Lambda gets its own SG, granted ingress/egress to talk to MSK's SG.
        # NOTE: standalone CfnSecurityGroupIngress here (not msk_security_group.add_ingress_rule)
        # to avoid a circular dependency, since this stack already depends on MskStack.
        lambda_sg = ec2.SecurityGroup(self, "BridgeLambdaSg", vpc=vpc, allow_all_outbound=True)
        ec2.CfnSecurityGroupIngress(
            self, "MskIngressFromBridgeLambda",
            group_id=msk_security_group.security_group_id,
            source_security_group_id=lambda_sg.security_group_id,
            ip_protocol="tcp",
            from_port=9092,
            to_port=9098,
            description="Bridge Lambda -> MSK",
        )

        role = iam.Role(
            self, "BridgeLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole"
                ),
            ],
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["kafka-cluster:Connect", "kafka-cluster:WriteData", "kafka-cluster:DescribeTopic"],
                resources=[msk_cluster_arn, f"{msk_cluster_arn.replace(':cluster/', ':topic/')}/*"],
            )
        )

        layer = None
        if os.path.exists(LAYER_ZIP_PATH):
            layer = _lambda.LayerVersion(
                self, "KafkaPythonLayer",
                code=_lambda.Code.from_asset(LAYER_ZIP_PATH),
                compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
            )

        self.function = _lambda.Function(
            self, "IotToKafkaBridge",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="iot_to_kafka.handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "lambda")),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_groups=[lambda_sg],
            role=role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                # Fill this in after MSK deploy: comma-separated bootstrap broker URLs
                "MSK_BROKERS": "REPLACE_WITH_BOOTSTRAP_BROKER_URLS",
            },
            layers=[layer] if layer else [],
        )

        CfnOutput(self, "BridgeLambdaArn", value=self.function.function_arn)
        CfnOutput(
            self, "NextStep",
            value="Create an IoT Core Rule with SQL \"SELECT * FROM 'simulator/+/data'\" and action = this Lambda",
        )
