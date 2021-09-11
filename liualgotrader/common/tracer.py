# type: ignore
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import \
    TraceContextTextMapPropagator


def get_tracer():
    tracer_provider = TracerProvider()
    cloud_trace_exporter = CloudTraceSpanExporter()
    tracer_provider.add_span_processor(
        # BatchSpanProcessor buffers spans and sends them in batches in a
        # background thread. The default parameters are sensible, but can be
        # tweaked to optimize your performance
        BatchSpanProcessor(cloud_trace_exporter)
    )
    trace.set_tracer_provider(tracer_provider)

    return trace.get_tracer(__name__)


class Tracer:
    def __init__(self, tracer):
        self.carrier = {}
        self.tracer = tracer

    def trace_root(self, name: str):
        with self.tracer.start_as_current_span(name):
            TraceContextTextMapPropagator().inject(carrier=self.carrier)

    def trace_child(self, name: str):
        ctx = TraceContextTextMapPropagator().extract(carrier=self.carrier)
        with self.tracer.start_as_current_span(name, context=ctx):
            pass
