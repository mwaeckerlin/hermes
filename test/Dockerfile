# Python tests against the built images. The gateway image carries the hermes
# virtualenv with the Hindsight memory provider, the config renderer and its
# templates; the dashboard plugins are taken from the dashboard image. Every
# file under test is copied out of the image that ships it, into the layout of
# this repository, so the tests read what is deployed and not the working tree.
FROM mwaeckerlin/hermes:gateway
USER root
RUN mkdir -p /work/files/todo-plugin /work/files/pairing-plugin \
 && cp /render-config.py /work/files/render-config.py \
 && cp /config.yaml.j2.default /work/files/config.yaml.j2 \
 && cp /hindsight-config.json.j2 /work/files/hindsight-config.json.j2 \
 && cp /check-isolation.py /work/files/check-isolation.py
COPY --from=mwaeckerlin/hermes:dashboard /opt/hermes/plugins/todo/dashboard/api.py /opt/hermes/plugins/todo/dashboard/storage.py /work/files/todo-plugin/
COPY --from=mwaeckerlin/hermes:dashboard /opt/hermes/plugins/pairing/dashboard/api.py /work/files/pairing-plugin/
# the hermes virtualenv is built with uv and carries no pip
RUN uv pip install --no-cache --python /opt/hermes/.venv/bin/python3 pytest httpx
COPY tests/ /work/tests/
RUN chown -R hermes:hermes /work
USER hermes
WORKDIR /work
ENV PYTHONPATH=/opt/hermes
ENTRYPOINT ["/opt/hermes/.venv/bin/python3", "-m", "pytest", "-p", "no:cacheprovider", "-W", "error"]
