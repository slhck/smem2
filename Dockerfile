FROM python:3.11-slim

WORKDIR /
COPY ./smem2 /usr/local/bin/smem2
RUN pip3 install --user pytest
COPY ./test.py /test.py
RUN chmod +x /test.py

ENTRYPOINT [ "/usr/local/bin/smem2" ]
