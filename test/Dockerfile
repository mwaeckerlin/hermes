# Python tests against the built images. The gateway image carries the hermes
# virtualenv, the config renderer and its templates; the dashboard plugins are
# taken from the dashboard image. Every file under test is copied out of the
# image that ships it, into the layout of this repository, so the tests read
# what is deployed and not the working tree.
FROM mwaeckerlin/hermes:gateway
USER root
RUN mkdir -p /work/files/todo-plugin /work/files/pairing-plugin /work/home \
 && cp /render-config.py /work/files/render-config.py \
 && cp /config.yaml.j2.default /work/files/config.yaml.j2 \
 && cp /hindsight-config.json.j2 /work/files/hindsight-config.json.j2 \
 && cp /check-isolation.py /work/files/check-isolation.py
COPY --from=mwaeckerlin/hermes:dashboard /opt/hermes/plugins/todo/dashboard/api.py /opt/hermes/plugins/todo/dashboard/storage.py /work/files/todo-plugin/
COPY --from=mwaeckerlin/hermes:dashboard /opt/hermes/plugins/pairing/dashboard/api.py /work/files/pairing-plugin/
COPY --from=mwaeckerlin/hermes:dashboard /opt/hermes-base-path/hermes_base_path.py /opt/hermes-base-path/install-hook.py /work/files/base-path/
# the hermes virtualenv carries no pip, and uv is a package of hermes' own
# package manager, off the PATH; pm.uv_launcher names its binary
RUN cd /opt/hermes \
 && "$(/opt/hermes/.venv/bin/python3 -c 'from pm import uv_launcher; print(uv_launcher("uv"))')" \
    pip install --no-cache --python /opt/hermes/.venv/bin/python3 pytest httpx
COPY tests/ /work/tests/
RUN chown -R hermes:hermes /work
USER hermes
WORKDIR /work
ENV PYTHONPATH=/opt/hermes
# the Hindsight memory provider, installed the way the gateway entrypoint does
# on its first start; /opt/data is a volume, whose build-time content Docker
# drops, so the test home lies beside the tests
ENV HERMES_HOME=/work/home
RUN /opt/hermes/.venv/bin/hermes plugins install hindsight --yes-deps --enable
ENTRYPOINT ["/opt/hermes/.venv/bin/python3", "-m", "pytest", "-p", "no:cacheprovider", "-W", "error"]
