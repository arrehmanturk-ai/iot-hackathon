from aws_cdk import (
    Stack, CfnOutput, Duration,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


POSTGRES_USER_DATA = """#!/bin/bash
dnf install -y postgresql15 postgresql15-server jq awscli
postgresql-setup --initdb
systemctl enable --now postgresql

# Pull the generated password out of Secrets Manager instead of hardcoding it
DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id iot/postgres --region __AWS_REGION__ --query SecretString --output text | jq -r .password)

sudo -u postgres psql -c "CREATE DATABASE iotdb;"
sudo -u postgres psql -d iotdb -c "CREATE TABLE iot_events (id SERIAL PRIMARY KEY, device_id VARCHAR(50), latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, event_timestamp TIMESTAMP);"
sudo -u postgres psql -c "CREATE USER iot_app WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE iotdb TO iot_app;"
sudo -u postgres psql -d iotdb -c "GRANT ALL ON iot_events TO iot_app;"
sudo -u postgres psql -d iotdb -c "GRANT ALL ON SEQUENCE iot_events_id_seq TO iot_app;"

# Enable logical replication for Debezium CDC
sudo -u postgres psql -c "ALTER SYSTEM SET wal_level = logical;"
sudo -u postgres psql -c "ALTER SYSTEM SET max_replication_slots = 4;"
sudo -u postgres psql -c "ALTER SYSTEM SET max_wal_senders = 4;"

# Allow remote connections
echo "listen_addresses = '*'" >> /var/lib/pgsql/data/postgresql.conf
echo "host    all             all             10.0.0.0/16            md5" >> /var/lib/pgsql/data/pg_hba.conf

systemctl restart postgresql
"""

BASTION_USER_DATA = """#!/bin/bash
dnf install -y postgresql15
"""


class PostgresStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str,
        vpc: ec2.Vpc, msk_security_group: ec2.SecurityGroup, **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        # --- Secret for DB credentials ---
        self.db_secret = secretsmanager.Secret(
            self, "PostgresSecret",
            secret_name="iot/postgres",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username":"iot_app"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=20,
            ),
        )

        # --- SSM role, shared by both instances ---
        ssm_role = iam.Role(
            self, "SsmInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
            ],
        )
        self.db_secret.grant_read(ssm_role)

        # --- Postgres security group: allow 5432 from MSK/Connect SG only ---
        pg_sg = ec2.SecurityGroup(
            self, "PostgresSecurityGroup", vpc=vpc, allow_all_outbound=True
        )
        pg_sg.add_ingress_rule(msk_security_group, ec2.Port.tcp(5432), "Kafka Connect -> Postgres")

        bastion_sg = ec2.SecurityGroup(
            self, "BastionSecurityGroup", vpc=vpc, allow_all_outbound=True
        )
        pg_sg.add_ingress_rule(bastion_sg, ec2.Port.tcp(5432), "Bastion -> Postgres")

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            POSTGRES_USER_DATA.replace("__AWS_REGION__", self.region)
        )

        self.postgres_instance = ec2.Instance(
            self, "PostgresInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.SMALL),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_group=pg_sg,
            role=ssm_role,
            user_data=user_data,
        )

        self.bastion_instance = ec2.Instance(
            self, "BastionInstance",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=bastion_sg,
            role=ssm_role,
            user_data=ec2.UserData.custom(BASTION_USER_DATA),
        )

        CfnOutput(self, "PostgresPrivateIp", value=self.postgres_instance.instance_private_ip)
        CfnOutput(self, "BastionInstanceId", value=self.bastion_instance.instance_id)
        CfnOutput(self, "PostgresInstanceId", value=self.postgres_instance.instance_id)
        CfnOutput(self, "PostgresSecretArn", value=self.db_secret.secret_arn)
