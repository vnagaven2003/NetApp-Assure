FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iputils-ping traceroute curl && rm -rf /var/lib/apt/lists/*
CMD ["sleep", "infinity"]
