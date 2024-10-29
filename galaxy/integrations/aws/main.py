from galaxy.core.galaxy import Integration, register
from galaxy.core.models import Config
from galaxy.integrations.aws.client import AwsClient

__all__ = ["Aws"]


class Aws(Integration):
    _methods = []
    default_region = "us-east-1"

    def __init__(self, config: Config):
        super().__init__(config)
        self.client = AwsClient(self.config, self.logger)

        self.regions = {}
        self.organization_account = {"AccountId": self.client.account_id, "AccountName": "Unknown AWS Organization"}
        self.regions_to_ec2s = {}
        self.regions_to_eks_clusters = {}
        self.regions_to_lambdas = {}
        self.regions_to_rds_db_instances = {}

        # Global services
        self.s3_buckets = {}

    @register(_methods, group=1)
    async def regions(self) -> list[dict]:
        for region in await self.client.get_regions(self.default_region):
            self.regions[region["RegionName"]] = region
        regions_mapped = await self.mapper.process("region", self.regions.values(), context={})
        self.logger.info(f"Found {len(regions_mapped)} regions")
        return regions_mapped

    @register(_methods, group=1)
    async def accounts(self) -> list[dict]:
        accounts = None
        try:
            accounts = await self.client.get_accounts(region=self.default_region)
        except Exception:
            self.logger.exception("Error getting organization accounts")

        if not accounts:
            self.logger.warning(
                "No organization accounts found, falling back to single account: %s",
                self.organization_account["AccountId"],
            )
            accounts = [self.organization_account]

        accounts_mapped = await self.mapper.process("account", accounts, context={})
        self.logger.info(f"Found {len(accounts_mapped)} accounts")

        if len(accounts_mapped) > 2:
            self.logger.warning("Multiple organization account detected, using fallback")
            self.organization_account = accounts[0]
        else:
            self.organization_account = accounts[0]

        return accounts_mapped

    @register(_methods, group=2)
    async def eks_clusters(self) -> list[dict]:
        clusters_mapped = []

        for region in self.regions.keys():
            self.regions_to_eks_clusters[region] = await self.client.get_generic_resources(region, "AWS::EKS::Cluster")
            clusters_mapped.extend(
                (
                    await self.mapper.process(
                        "eks_cluster",
                        self.regions_to_eks_clusters[region],
                        context={"region": region, "account": self.organization_account["AccountId"]},
                    )
                )
            )
        self.logger.info(f"Found {len(clusters_mapped)} EKS Clusters")
        return clusters_mapped

    @register(_methods, group=2)
    async def lambdas(self) -> list[dict]:
        lambdas_mapped = []

        for region in self.regions.keys():
            self.regions_to_lambdas[region] = await self.client.get_generic_resources(region, "AWS::Lambda::Function")
            lambdas_mapped.extend(
                (
                    await self.mapper.process(
                        "lambda",
                        self.regions_to_lambdas[region],
                        context={"region": region, "account": self.organization_account["AccountId"]},
                    )
                )
            )
        self.logger.info(f"Found {len(lambdas_mapped)} lambdas")
        return lambdas_mapped

    @register(_methods, group=2)
    async def ec2s(self) -> list[dict]:
        ec2s_mapped = []

        for region in self.regions.keys():
            self.regions_to_ec2s[region] = await self.client.get_ec2s(region=region)
            ec2s_mapped.extend(
                (
                    await self.mapper.process(
                        "ec2",
                        self.regions_to_ec2s[region],
                        context={"region": region, "account": self.organization_account["AccountId"]},
                    )
                )
            )
        self.logger.info(f"Found {len(ec2s_mapped)} EC2s")
        return ec2s_mapped

    @register(_methods, group=2)
    async def s3_buckets(self) -> list[dict]:
        """
        Theory:

        S3 is designed with a global management model where bucket names are unique across all regions.
        This means if you query S3s per region you'll get all S3 buckets in the AWS org in all your requests.
        Although S3 manages buckets globally, the data associated with each bucket is still stored in the specific
        region. This region isn't specified in the response, but we can infer it with the regional domain name.

        Other AWS Services with Similar Behavior:
            - AWS Global Accelerator
            - AWS CloudFront

        The method below could probably be optimized tot avoid having to run a mapper for each S3.
        """

        self.s3_buckets = await self.client.get_generic_resources(self.default_region, "AWS::S3::Bucket")
        buckets_regions = await self.mapper.process("s3_bucket_region", self.s3_buckets, context={})

        buckets_mapped = []
        for region, bucket in zip(buckets_regions, self.s3_buckets):
            buckets_mapped.extend(
                (
                    await self.mapper.process(
                        "s3_bucket",
                        [bucket],
                        context={"account": self.organization_account["AccountId"], "region": region["region"]},
                    )
                )
            )
        self.logger.info(f"Found {len(buckets_mapped)} S3 Buckets")
        return buckets_mapped

    @register(_methods, group=2)
    async def rds_db_instances(self) -> list[dict]:
        rds_instances_mapped = []

        for region in self.regions.keys():
            self.regions_to_rds_db_instances[region] = await self.client.get_generic_resources(
                region, "AWS::RDS::DBInstance"
            )
            rds_instances_mapped.extend(
                (
                    await self.mapper.process(
                        "rds_db_instance",
                        self.regions_to_rds_db_instances[region],
                        context={"region": region, "account": self.organization_account["AccountId"]},
                    )
                )
            )
        self.logger.info(f"Found {len(rds_instances_mapped)} RDS DB Instances")
        return rds_instances_mapped
