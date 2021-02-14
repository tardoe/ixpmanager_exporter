FROM python:3.6.1-alpine
WORKDIR /ixpmanager_exporter
ADD . /ixpmanager_exporter
RUN pip install -r requirements.txt
CMD ["python","ixpmanager_exporter.py"]