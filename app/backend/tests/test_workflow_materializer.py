from app.core.node_alias_resolver import NodeAliasResolver
from app.core.workflow_materializer import materialize_workflow

def test_materialize_replaces_aliases():
    alias = {"logical_nodes": {"LOAD_IMAGE": {"candidates": ["LoadImage"]}}}
    object_info = {"LoadImage": {"input": {"required": {"image": ["STRING"]}}}}
    resolver = NodeAliasResolver(alias, object_info)
    template = {"1": {"class_type": "@node:LOAD_IMAGE", "inputs": {"image": "x"}}}
    workflow, resolved = materialize_workflow(template, resolver)
    assert workflow["1"]["class_type"] == "LoadImage"
    assert resolved["LOAD_IMAGE"] == "LoadImage"
