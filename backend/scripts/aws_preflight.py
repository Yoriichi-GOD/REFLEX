from __future__ import annotations

import shutil
import subprocess
import sys
import os

profile = os.getenv("AWS_PROFILE", "reflex-aws")

if not shutil.which("aws"):
    print("AWS deployment blocked: AWS CLI is not installed.")
    sys.exit(2)
common = ["--profile", profile, "--region", os.getenv("AWS_REGION", "ap-southeast-2"), "--no-cli-pager"]
try:
    subprocess.check_output(["aws", "sts", "get-caller-identity", *common, "--query", "UserId", "--output", "text"], text=True, stderr=subprocess.DEVNULL, timeout=15)
except Exception:
    print(f"AWS deployment blocked: profile '{profile}' has no verifiable session. Do not add access keys to the repository.")
    sys.exit(2)
print(f"AWS authentication verified for profile '{profile}'. Caller details withheld; no cloud changes were made.")
for stack in ("reflex-foundation", "reflex-service"):
    try:
        result = subprocess.run(
            ["aws", "cloudformation", "describe-stacks", "--stack-name", stack, *common, "--query", "Stacks[0].StackStatus", "--output", "text"],
            text=True, capture_output=True, timeout=20,
        )
        if result.returncode:
            message = result.stderr + " " + result.stdout
            if "does not exist" in message or "ValidationError" in message:
                print(f"{stack}: absent")
            else:
                print(f"{stack}: unable to verify status")
            continue
        status = result.stdout.strip()
        print(f"{stack}: {status}")
        if stack == "reflex-service" and status == "CREATE_COMPLETE":
            endpoint = subprocess.run(
                ["aws", "cloudformation", "describe-stacks", "--stack-name", stack, *common, "--query", "Stacks[0].Outputs[?OutputKey=='Endpoint'].OutputValue | [0]", "--output", "text"],
                text=True, capture_output=True, timeout=20,
            )
            if endpoint.returncode == 0:
                print(f"HTTPS endpoint: {endpoint.stdout.strip()}")
            else:
                print("HTTPS endpoint: unable to verify")
    except Exception:
        print(f"{stack}: unable to verify status")
