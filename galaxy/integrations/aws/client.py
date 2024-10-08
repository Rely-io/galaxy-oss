import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from tenacity import retry, stop_after_attempt, wait_random_exponential

from galaxy.core.models import Config

__all__ = ["AwsClient"]

logger = logging.getLogger("galaxy")


def log_attempt_number(retry_state):
    """return the result of the last call attempt"""
    print(f"Retrying: {retry_state.attempt_number}...")


class AwsClient:
    def __init__(self, config: Config, logger: logging.Logger):
        self.logger = logger
        self.config = config

        self.account_id = config.integration.properties["accountId"]

        # access_key = json.loads(config.integration.properties["accessKey"])
        access_key = config.integration.properties["accessKey"]
        if isinstance(access_key, str):
            access_key = json.loads(access_key)
        if not isinstance(access_key, dict):
            raise Exception("Access key has invalid format")

        access_key_id = access_key.get("AccessKeyId")
        if not access_key_id:
            raise Exception("Missing AccessKeyId")

        access_key_secret = access_key.get("SecretAccessKey")
        if not access_key_secret:
            raise Exception("Missing SecretAccessKey")

        self.aws_session = boto3.Session(aws_access_key_id=access_key_id, aws_secret_access_key=access_key_secret)

    async def get_regions(self, base_region) -> list[dict]:
        return self.aws_session.client("ec2", region_name=base_region).describe_regions()["Regions"]

    async def get_accounts(self, region: str) -> list[dict]:
        aws_cloudcontrol_client = self.aws_session.client("cloudcontrol", region_name=region)
        resource_type = "AWS::Organizations::Account"

        # Fetch Resource References
        try:
            resources_descriptions = aws_cloudcontrol_client.list_resources(**{"TypeName": resource_type}).get(
                "ResourceDescriptions", []
            )
        except Exception as e:
            logger.error(f"Failed to list resources for kind: {resource_type}")
            raise e

        # Fetch Resource Payloads
        resources = []
        for description in resources_descriptions:
            resource_id = description.get("Identifier")
            if not resource_id:
                logger.error(f"Failed get individual resource (no id). Kind: {resource_type}: {description}")

            response = (
                aws_cloudcontrol_client.get_resource(TypeName=resource_type, Identifier=resource_id)
                .get("ResourceDescription", {})
                .get("Properties", None)
            )
            if response:
                resources.append(json.loads(response))

        return resources

    async def get_ec2s(self, region):
        ec2s = []

        # List all EC2s in region
        aws_ec2_client = self.aws_session.resource("ec2", region_name=region)
        try:
            ec2s_metadata = aws_ec2_client.instances.all()
        except Exception as e:
            logger.error(f"Failed to list EC2 Instance in region: {region}; error {e}")

        # Fetch all more specific details about each EC2 in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.get_ec2, instance.id, region) for instance in ec2s_metadata]

            for completed_future in as_completed(futures):
                result = completed_future.result()
                if result:
                    ec2s.append(result)

        return ec2s

    @retry(
        stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=60), after=log_attempt_number, reraise=True
    )
    def get_ec2(self, instance_id, region):
        aws_ec2_client = self.aws_session.client("ec2", region_name=region)
        instance_response = aws_ec2_client.describe_instances(InstanceIds=[instance_id])
        try:
            instance_obj = instance_response.get("Reservations")[0]["Instances"][0]
        except Exception as e:
            logger.error(f"Failed to extract AWS/EC2 from API response id: {instance_id}, error: {e}")
            raise
        return json.loads(json.dumps(instance_obj, default=str))

    async def get_generic_resources(self, region, resource_type):
        # List all Resources in region
        resource_descriptions = (
            self.aws_session.client("cloudcontrol", region_name=region)
            .list_resources(**{"TypeName": resource_type})
            .get("ResourceDescriptions", [])
        )

        # Fetch all more specific details about each Resource in parallel
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                loop.run_in_executor(
                    executor, self.get_generic_resource, resource_type, resource_desc.get("Identifier", ""), region
                )
                for resource_desc in resource_descriptions
            ]
            resources = await asyncio.gather(*futures)
        return resources

    @retry(
        stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=45), after=log_attempt_number, reraise=True
    )
    def get_generic_resource(self, resource_type, resource_id, region):
        aws_cloudcontrol_client = self.aws_session.client("cloudcontrol", region_name=region)
        response = (
            aws_cloudcontrol_client.get_resource(TypeName=resource_type, Identifier=resource_id)
            .get("ResourceDescription")
            .get("Properties")
        )

        return json.loads(response)
