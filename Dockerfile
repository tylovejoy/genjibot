FROM python:3.12.7

WORKDIR /usr/src/app

RUN apt-get update && apt-get upgrade -y && apt-get install -y wget\
    libnss3\
    libnspr4\
    libdbus-1-3\
    libatk1.0-0\
    libatk-bridge2.0-0\
    libcups2\
    libdrm2\
    libxcomposite1\
    libxdamage1\
    libxfixes3\
    libxrandr2\
    libgbm1\
    libxkbcommon0\
    libasound2\
    libatspi2.0-0


# Set display variable for headless Chromium
ENV DISPLAY=:0

RUN useradd -m -d /home/genji -s /bin/bash genji && \
    mkdir /usr/src/genji && \
    chown -R genji /usr/src/genji

USER genji

COPY requirements.txt ./
RUN pip3 install --no-warn-script-location --no-cache-dir -r requirements.txt

RUN ~/.local/bin/playwright install

COPY . .


CMD [ "python3", "-uO", "main.py" ]
