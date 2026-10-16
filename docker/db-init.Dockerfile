FROM mcr.microsoft.com/mssql/server:2022-latest

USER root
WORKDIR /opt/qldsv

COPY docker/init-db.sh /opt/qldsv/init-db.sh
COPY database/ /opt/qldsv/database/

RUN chmod +x /opt/qldsv/init-db.sh \
    && chown -R mssql:root /opt/qldsv

USER mssql
ENTRYPOINT ["/bin/bash", "/opt/qldsv/init-db.sh"]

