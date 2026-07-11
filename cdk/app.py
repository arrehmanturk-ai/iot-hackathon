#!/usr/bin/env python3
import os
import aws_cdk as cdk

from stacks.vpc_stack import VpcStack
from stacks.msk_stack import MskStack
from stacks.postgres_stack import PostgresStack
from stacks.bridge_lambda_stack import BridgeLambdaStack

env = cdk.Environment(
    account=os.environ.get("AWS_ACCOUNT_ID", os.environ.get("CDK_DEFAULT_ACCOUNT")),
    region="us-east-1",
)

app = cdk.App()

vpc_stack = VpcStack(app, "IotVpcStack", env=env)

msk_stack = MskStack(app, "IotMskStack", vpc=vpc_stack.vpc, env=env)
msk_stack.add_dependency(vpc_stack)

postgres_stack = PostgresStack(
    app, "IotPostgresStack",
    vpc=vpc_stack.vpc,
    msk_security_group=msk_stack.security_group,
    env=env,
)
postgres_stack.add_dependency(vpc_stack)

bridge_stack = BridgeLambdaStack(
    app, "IotBridgeLambdaStack",
    vpc=vpc_stack.vpc,
    msk_cluster_arn=msk_stack.cluster.attr_arn,
    msk_security_group=msk_stack.security_group,
    env=env,
)
bridge_stack.add_dependency(msk_stack)

app.synth()
