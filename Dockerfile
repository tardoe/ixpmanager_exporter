FROM tiangolo/uwsgi-nginx-flask:python3.8
COPY ./app /app
RUN pip install -r /app/requirements.txt
ENV LISTEN_PORT 9804
EXPOSE 9804