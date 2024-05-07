FROM python:3.11.9

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /bot/cait


COPY requirements.txt /bot/cait/
RUN pip install --upgrade pip && pip install -r requirements.txt && chmod 755 .


COPY . /bot/cait/

