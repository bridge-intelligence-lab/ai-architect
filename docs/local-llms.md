Perfect. We’ll run **everything on one box (`tensorbook`, 3080 Ti)** for now, and leave **`jarvis` (1080 Ti)** unused until you want to split loads later.

Here’s the clean single-box setup:

# 0) Clean up any leftovers

```bash
# kill any old SSH tunnels using 11434/21143
ps aux | grep '[s]sh -N -L' | awk '{print $2}' | xargs -r kill

# stop local Ollama if you previously tweaked it
sudo systemctl stop ollama || true
```

---

# 1) vLLM on GPU (Qwen 7B) — `tensorbook`

Persist caches so weights don’t re-download; set conservative KV cache.

```bash
sudo mkdir -p /opt/models/hf_cache /opt/models/vllm_cache
sudo chown -R $USER:$USER /opt/models

docker run --gpus all --rm -it \
  -p 8000:8000 \
  -e HF_HOME=/root/.cache/huggingface \
  -e HF_HUB_ENABLE_HF_TRANSFER=1 \
  -v /opt/models/hf_cache:/root/.cache/huggingface \
  -v /opt/models/vllm_cache:/root/.cache/vllm \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-7B-Instruct \
  --dtype auto \
  --max-model-len 4096 \
  --max-num-seqs 4 \
  --gpu-memory-utilization 0.95 \
  --swap-space 8 \
  --trust-remote-code
```

Quick test:

```bash
curl -s http://127.0.0.1:8000/v1/models | jq .
```

---

# 2) Ollama on **CPU** (embeddings + DeepSeek) — same box

We’ll force CPU so it doesn’t fight vLLM for VRAM.

```bash
sudo systemctl edit ollama
```

Paste:

```
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_NUM_GPU=0"
Environment="OLLAMA_ORIGINS=*"
```

Apply & start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
```

Pull models (small embed + your coder):

```bash
ollama pull nomic-embed-text
ollama pull deepseek-coder
ollama list
```

Sanity:

```bash
curl -s http://127.0.0.1:11434/api/tags | jq .
curl -s http://127.0.0.1:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"hello"}' | jq '.embedding|length'
```

> If you later want DeepSeek to use **a little GPU** without starving vLLM:
> set `Environment="OLLAMA_GPU_LAYERS=8"` instead of `OLLAMA_NUM_GPU=0`. Start CPU-only first; add layers later if needed.

---

# 3) LiteLLM proxy — single entrypoint

Create `litellm.yaml` on `tensorbook`:

```yaml
model_list:
  - model_name: local-generate
    litellm_params:
      custom_llm_provider: ollama
      api_base: "http://127.0.0.1:11434/v1"
      api_key: "sk-no-key-needed"
      model: "Qwen/Qwen2.5-7B-Instruct"

  - model_name: local-embed
    litellm_params:
      custom_llm_provider: ollama
      api_base: "http://127.0.0.1:11434"
      model: "nomic-embed-text"
      timeout: 30

  - model_name: local-code
    litellm_params:
      custom_llm_provider: ollama
      api_base: "http://127.0.0.1:11434"
      model: "deepseek-coder"
      timeout: 60

general_settings:
  request_timeout: 30
  max_input_tokens: 12000
  max_output_tokens: 1024
```

Run:

```bash
pip install -U "litellm[proxy]"
LITELLM_LOG=DEBUG litellm --config litellm.yaml --host 0.0.0.0 --port 4000
```

---

# 4) Tests (run on `tensorbook`)

Proxy up?

```bash
curl -s http://127.0.0.1:4000/v1/models | jq .
```

Chat (vLLM via LiteLLM):

```bash
curl -s http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-no-key-needed" -H "Content-Type: application/json" \
  -d '{"model":"local-generate","messages":[{"role":"user","content":"Say hi in 5 words."}],"temperature":0.2}' \
  | jq -r '.choices[0].message.content'
```

Embeddings (Ollama CPU via LiteLLM):

```bash
curl -s http://127.0.0.1:4000/v1/embeddings \
  -H "Authorization: Bearer sk" -H "Content-Type: application/json" \
  -d '{"model":"local-embed","input":"multi-agent simulations are cool"}' \
  | jq '.data[0].embedding | length'
```

Code model (DeepSeek via LiteLLM):

```bash
curl -s http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer sk" -H "Content-Type: application/json" \
  -d '{
        "model":"local-code",
        "messages":[
          {"role":"system","content":"Return only a single Python code block."},
          {"role":"user","content":"Write a function that parses an ISO date to datetime."}
        ],
        "temperature":0.1
      }' | jq -r '.choices[0].message.content'
```

---

# 5) Tips / knobs

* **If vLLM OOMs**: drop `--max-model-len` to 3072/2048 or `--max-num-seqs` to 2.
* **If embeddings feel slow**: that’s CPU; totally OK for now. You can move Ollama to `jarvis` later and change `api_base` to its IP.
* **If DeepSeek is heavy**: keep it CPU (current setup) or allow a few `OLLAMA_GPU_LAYERS` once vLLM is stable.

---

When you’re ready to split loads:

* Start Ollama on `jarvis`, open 11434 on LAN, set `api_base: "http://<jarvis-ip>:11434"` for `local-embed` and `local-code`.
* No other changes needed—Architect still hits LiteLLM on `tensorbook`.
