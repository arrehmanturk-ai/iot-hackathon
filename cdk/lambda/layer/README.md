# kafka-python Lambda layer

`kafka-python` isn't in the default Lambda runtime, so package it as a layer before deploying `IotBridgeLambdaStack`:

```bash
cd cdk/lambda/layer
mkdir -p python
pip install kafka-python -t python/
zip -r kafka-python-layer.zip python
```

The CDK stack (`bridge_lambda_stack.py`) references `kafka-python-layer.zip` in this directory — run the commands above once before your first `cdk deploy`.
