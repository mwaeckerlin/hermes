# Python tests against the built images. The dashboard image carries the
# plugins and the hermes virtualenv (fastapi, jinja2); the config renderer and
# its template are taken from the gateway image. Every file under test is
# copied out of the image that ships it, into the layout of this repository,
# so the tests read what is deployed and not the working tree.
FROM mwaeckerlin/hermes:dashboard
USER root
COPY --from=mwaeckerlin/hermes:gateway /render-config.py /work/files/render-config.py
COPY --from=mwaeckerlin/hermes:gateway /config.yaml.j2.default /work/files/config.yaml.j2
RUN mkdir -p /work/files/todo-plugin /work/files/pairing-plugin \
 && cp /opt/hermes/plugins/todo/dashboard/api.py /opt/hermes/plugins/todo/dashboard/storage.py /work/files/todo-plugin/ \
 && cp /opt/hermes/plugins/pairing/dashboard/api.py /work/files/pairing-plugin/
# the hermes virtualenv is built with uv and carries no pip
RUN uv pip install --no-cache --python /opt/hermes/.venv/bin/python3 pytest httpx
COPY tests/*.py /work/tests/
RUN chown -R hermes:hermes /work
USER hermes
WORKDIR /work
ENV PYTHONPATH=/opt/hermes
ENTRYPOINT ["/opt/hermes/.venv/bin/python3", "-m", "pytest", "-p", "no:cacheprovider", "-W", "error", "tests"]
