# Local AI Discovery Server

一个实验性的轻量 Python 服务，通过 mDNS / DNS-SD 在局域网声明本机提供的 OpenAI-compatible API。

它用于验证一种简单的本地 AI 发现方式：客户端无需预先配置固定 IP，即可找到 AI 服务的主机、端口、API 路径和认证要求。当前版本只实现服务广播与退出注销，不负责模型推理或 API 代理，也不是完整的生产级服务发现方案。

## 广播内容

服务类型固定为：

```text
_local-ai._tcp.local.
```

DNS-SD 的 SRV 记录提供 hostname 和端口，TXT 记录提供：

```text
v=1
api=openai
auth=none
base=/v1
models=/v1/models
```

其中 `auth` 支持 `none` 和 `api-key`，但不会广播 API key 本身。客户端可组合出 API Base URL，并通过 `models` 路径获取实际模型列表。

## 本地运行

需要 Python 3.10+。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python local_ai_discovery.py --config config.example.yaml
```

配置见 [`config.example.yaml`](./config.example.yaml)，也可通过 `LOCAL_AI_NAME`、`LOCAL_AI_PORT`、`LOCAL_AI_API`、`LOCAL_AI_AUTH`、`LOCAL_AI_BASE_PATH`、`LOCAL_AI_MODELS_PATH` 覆盖。不传 `--config` 时使用 hostname、端口 `11434` 和默认 OpenAI-compatible 路径。

## 安装为 systemd 服务

在项目目录执行：

```bash
sudo install -d /opt/local-ai-discovery /etc/local-ai-discovery
sudo install -m 0644 local_ai_discovery.py requirements.txt /opt/local-ai-discovery/
sudo python3 -m venv /opt/local-ai-discovery/.venv
sudo /opt/local-ai-discovery/.venv/bin/pip install -r /opt/local-ai-discovery/requirements.txt
sudo install -m 0644 config.example.yaml /etc/local-ai-discovery/config.yaml
sudo install -m 0644 local-ai-discovery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now local-ai-discovery.service
```

systemd 可从可选的 `/etc/default/local-ai-discovery` 读取环境变量覆盖。

## 验证

```bash
python -m unittest -v
systemctl status local-ai-discovery.service
dns-sd -B _local-ai._tcp
```

Linux 客户端也可使用 `avahi-browse -rt _local-ai._tcp`。
