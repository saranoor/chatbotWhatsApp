from aws_cdk import Stack, aws_opensearchservice as opensearch, RemovalPolicy
from constructs import Construct


class StorageStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # OpenSearch domain
        self.opensearch_domain = opensearch.Domain(
            self,
            "OpenSearchDomain",
            version=opensearch.EngineVersion.OPENSEARCH_2_11,
            capacity=opensearch.CapacityConfig(
                data_node_instance_type="t3.small.search", data_nodes=1
            ),
            ebs=opensearch.EbsOptions(volume_size=20, volume_type="gp3"),
            removal_policy=RemovalPolicy.RETAIN,
        )
