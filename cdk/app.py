import aws_cdk as cdk
from cdk_stack import WhatsappBotStack

app = cdk.App()
WhatsappBotStack(app, "WhatsappBotStack")
app.synth()
