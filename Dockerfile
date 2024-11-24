FROM python:3.12.7

WORKDIR /usr/src/app

RUN apt-get update && apt-get upgrade -y && apt-get install -y wget
# For safety reason, create an user with lower privileges than root and run from there
RUN useradd -m -d /home/genji -s /bin/bash genji && \
    mkdir /usr/src/genji && \
    chown -R genji /usr/src/genji

USER genji


COPY requirements.txt ./
RUN pip3 install --no-warn-script-location --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python3", "-u", "main.py" ]
