FROM kalilinux/kali-rolling:latest

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    nmap sqlmap \
    curl iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/kali/ai-red-blue-lab

COPY . .

RUN python3 -m venv venv && \
    ./venv/bin/pip install --upgrade pip && \
    ./venv/bin/pip install openai

CMD ["/bin/bash"]
