from flow_memory.crypto import generate_local_keypair, sign_manifest, verify_manifest
from flow_memory.flowlang import compile_flowlang_file

result = compile_flowlang_file("examples/flowlang_agent.flow")
key = generate_local_keypair("demo")
signature = sign_manifest(result.manifest, key)
print({"verified": verify_manifest(result.manifest, signature, key), "key_id": signature.key_id})
