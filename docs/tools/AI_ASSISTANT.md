# AI Assistant for slsflow

AI-powered assistant for creating data pipelines. **100% FREE!**

## Quick Start (30 seconds)

```bash
# 1. Install Ollama (one time)
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Run AI assistant (auto-downloads model on first run)
slsflow-ai
```

That's it! The assistant will guide you through setup on first run.

## What It Does

| Mode | Command | Example |
|------|---------|---------|
| **Generate** | `/generate <desc>` | `/generate Daily ETL from S3 to Redshift` |
| **Help** | `/help <topic>` | `/help trigger rules` |
| **Debug** | `/debug <e>` | `/debug Task timeout after 300s` |
| **Example** | `/example [name]` | `/example parallel` (basic, parallel, cleanup, asset, wait_for, glue) |
| **Validate** | `/validate` | Check last generated code for errors |
| **Save** | `/save <name>` | `/save my-etl` → saves to `pipelines/my-etl/` |
| **Chat** | Just type | `What's the difference between push and pull assets?` |

## Example Session

```
$ slsflow-ai

✅ Using: groq/llama-3.3-70b-versatile (FREE)
✓ Deploy method: slsflow-deploy

============================================================
🤖 slsflow AI Assistant
   AI: groq/llama-3.3-70b-versatile
   Deploy: slsflow-deploy
============================================================

Commands:
  /generate <desc>   - Generate pipeline
  /debug <e>     - Debug an issue
  /help <topic>      - Get help on topic
  /example [name]    - Show example (basic, parallel, cleanup, asset, wait_for, glue)
  /validate          - Validate last generated code
  /save <path>       - Save code to pipelines/<path>/
  /clear             - Clear history
  /quit              - Exit

You: /generate Daily pipeline that extracts from S3 and loads to Snowflake

🤖 Assistant:
Here's your pipeline:

```python
from slsflow import DAG, task
import os

STAGE = os.environ.get("SLSFLOW_STAGE", "dev")

# Config from config.py ENVIRONMENTS

with DAG(
    dag_id="daily-s3-to-snowflake",
    schedule="@daily",
    alerts={"slack": "#data-alerts"}
) as dag:
    
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-s3-extract")
    def extract():
        """Extract data from S3."""
        pass
    
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-transform")
    def transform():
        """Transform data."""
        pass
    
    @task.sfn(arn=f"arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:myorg-{STAGE}-snowflake-load")
    def load():
        """Load to Snowflake."""
        pass
    
    extract() >> transform() >> load()

# Deploy: slsflow-deploy --stage $STAGE
```

Next steps:
1. Ensure config.py has ENVIRONMENTS configured
2. Save as `pipelines/daily-s3-to-snowflake/dag.py`
3. Run `slsflow-deploy`

You: /quit
Bye! 👋
```

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SmartProvider                                    │
│                                                                         │
│   GROQ_API_KEY set?                                                     │
│       │                                                                 │
│       ├── Yes ──▶ Use Groq (fast cloud API, Llama 3.1 70B)             │
│       │              │                                                  │
│       │          Rate limit hit?                                        │
│       │              │                                                  │
│       │              └── Yes ──▶ Auto-switch to Ollama                 │
│       │                                                                 │
│       └── No ───▶ Use Ollama (local, always works)                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## AI Providers

All options are **FREE**:

| Provider | Speed | Quality | Setup |
|----------|-------|---------|-------|
| **Groq** (recommended) | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | Get free key at [console.groq.com](https://console.groq.com/keys) |
| **Ollama** | ⚡⚡ | ⭐⭐⭐ | Already included (fallback) |

### Optional: Add Groq for Faster Responses

```bash
# Get free API key at https://console.groq.com/keys
# Then add to your shell:
echo 'export GROQ_API_KEY=gsk_xxxxx' >> ~/.bashrc
source ~/.bashrc
```

Benefits of Groq:
- 🚀 Much faster responses
- 🧠 Larger model (70B vs 8B)
- ☁️ No local resources needed
- 🆓 Generous free tier (14,400 requests/day)

## CLI Options

```bash
# Interactive mode (default)
slsflow-ai

# Quick question
slsflow-ai "What are trigger rules?"

# Generate pipeline
slsflow-ai generate "Daily ETL from S3 to Redshift"

# Debug error
slsflow-ai debug "Task 'extract' failed with timeout"

# Force specific provider
slsflow-ai --provider ollama "Create pipeline"

# List providers
slsflow-ai --list-providers
```

## First-Time Setup

On first run without configuration, the assistant runs interactive setup:

```
$ slsflow-ai

═══════════════════════════════════════════════════════════
🤖 slsflow AI - First Time Setup
═══════════════════════════════════════════════════════════

Checking Ollama (local AI)...
✅ Ollama installed

Downloading AI model (one time, ~4.7GB)...
  ollama pull llama3.1
✅ Model downloaded

─────────────────────────────────────────────────────────────
Optional: Set up Groq for faster responses (free)
─────────────────────────────────────────────────────────────

1. Go to: https://console.groq.com/keys
2. Sign in with Google/GitHub
3. Copy API key

Paste Groq API key (or Enter to skip): gsk_xxxx
✅ Saved to ~/.bashrc

═══════════════════════════════════════════════════════════
✅ Setup complete! Starting AI assistant...
═══════════════════════════════════════════════════════════
```

## What AI Can Generate

### 1. Simple Pipeline
```
/generate Daily job that runs at 2am
```

### 2. ETL Pipeline
```
/generate Extract from S3 bucket 'raw-data', transform with Glue, load to RDS
```

### 3. Asset-Based Pipeline
```
/generate Pipeline triggered when 'inventory' asset is updated, outputs 'report' asset
```

### 4. Complex Dependencies
```
/generate Pipeline with 3 parallel extract tasks, then transform, then 2 parallel loads
```

### 5. Error Handling
```
/generate Pipeline where cleanup runs even if main task fails (use trigger_rule)
```

## IaC Output Formats

All pipelines deploy with slsflow-deploy using hardcoded ARNs:
- ARN syntax: `arn="arn:aws:states:..."`
- Deploy: `slsflow-deploy`

## Troubleshooting

### "Ollama not found"
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### "Model not found"
```bash
ollama pull llama3.1
```

### Slow responses
Add Groq for faster cloud-based responses:
```bash
# Get key at https://console.groq.com/keys
export GROQ_API_KEY=gsk_xxxxx
```

### Rate limit hit
The assistant automatically falls back to Ollama. No action needed.

## Cost

| Component | Cost |
|-----------|------|
| Ollama | **$0** (runs locally) |
| Groq | **$0** (free tier) |
| slsflow-ai | **$0** |
| **Total** | **$0** |

## Tips for Best Results

1. **Be specific**: "Daily ETL from S3 bucket 'raw-data' to Redshift table 'analytics.events'"
2. **Mention schedule**: "@daily", "@hourly", "cron(0 2 * * *)"
3. **Specify error handling**: "with cleanup task that always runs"
4. **Ask for explanation**: "Create X and explain each part"
5. **Iterate**: "Now add retry logic to the extract task"
6. **Use /validate**: Always validate before saving
7. **Use /save**: Save directly to proper location with 
## Advanced Commands

### `/example` - Show Production Examples

```
You: /example
Available examples:
  • basic
  • parallel
  • cleanup
  • asset
  • wait_for
  • glue

You: /example parallel
📝 Example:
# Parallel Processing (Fan-out/Fan-in)
with DAG("parallel", schedule="@hourly", alerts={"slack": "#alerts"}) as dag:
    @task.sfn(arn="...")
    def prepare(): pass
    
    @task.sfn(arn="...")
    def process_a(): pass
    
    @task.sfn(arn="...")
    def process_b(): pass
    
    @task.sfn(arn="...")
    def aggregate(): pass
    
    prepare() >> [process_a(), process_b()] >> aggregate()
```

### `/validate` - Check Generated Code

```
You: /generate Daily ETL
🤖 [generates code]

You: /validate
✅ Validation passed!
  ✓ Syntax OK
  ✓ DAG structure valid
  ✓ Ready to deploy!
```

If there are issues:
```
You: /validate
❌ Validation failed!
  ❌ No DAG definition found
  ⚠️  No alerts configuration found
```

### `/save` - Save to Pipeline Directory

```
You: /generate Daily ETL from S3 to Snowflake
🤖 [generates code]

You: /validate
✅ Validation passed!

You: /save daily-s3-snowflake
✅ Saved successfully!
   📄 pipelines/daily-s3-snowflake/dag.py
   📄 pipelines/daily-s3-snowflake/
Next steps:
   cd pipelines/daily-s3-snowflake
      slsflow-deploy
```

## Complete Workflow Example

```
$ slsflow-ai

You: /generate Daily pipeline that extracts from 3 S3 buckets in parallel, 
     transforms with Glue, and loads to Redshift. Add cleanup task.

🤖 [generates code with parallel extract, Glue transform, Redshift load, cleanup]

You: /validate
✅ Validation passed!

You: /save daily-multi-source-etl
✅ Saved successfully!
   📄 pipelines/daily-multi-source-etl/dag.py
   📄 pipelines/daily-multi-source-etl/
Next steps:
   cd pipelines/daily-multi-source-etl
      slsflow-deploy

You: /quit
Bye! 👋

$ cd pipelines/daily-multi-source-etl
$ slsflow-deploy
# Pipeline deployed! 🚀
```
