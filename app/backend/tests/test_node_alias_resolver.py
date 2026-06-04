from app.core.node_alias_resolver import NodeAliasResolver

def test_resolve_exact():
    alias = {
        "logical_nodes": {
            "ICLIGHT_APPLY": {"candidates": ["LoadAndApplyICLightUnet", "ICLightConditioning"]}
        }
    }
    object_info = {"ICLightConditioning": {}, "SomethingElse": {}}
    resolver = NodeAliasResolver(alias, object_info)
    resolved = resolver.resolve("ICLIGHT_APPLY")
    assert resolved.concrete_name == "ICLightConditioning"
