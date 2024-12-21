FROM python:3.12.7

WORKDIR /usr/src/app

RUN apt-get update && apt-get upgrade -y && apt-get install -y wget && apt-get install -y firefox-esr

ENV DISPLAY=:0
# For safety reason, create an user with lower privileges than root and run from there
RUN useradd -m -d /home/genji -s /bin/bash genji && \
    mkdir /usr/src/genji && \
    chown -R genji /usr/src/genji

USER genji

COPY requirements.txt ./
RUN pip3 install --no-warn-script-location --no-cache-dir -r requirements.txt

USER root
ADD https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz ./
# Adjust permissions of the tar file
RUN chmod 644 ./geckodriver-v0.35.0-linux64.tar.gz

# Extract Geckodriver
RUN tar -xvzf ./geckodriver-v0.35.0-linux64.tar.gz -C /usr/src/app/ && \
    chmod +x /usr/src/app/geckodriver && \
    rm ./geckodriver-v0.35.0-linux64.tar.gz

# Ensure extracted Geckodriver is usable by the non-root user
RUN chown genji:genji /usr/src/app/geckodriver

USER genji
COPY . .

CMD [ "python3", "-uO", "main.py" ]
