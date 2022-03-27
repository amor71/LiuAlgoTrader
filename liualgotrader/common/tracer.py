# type: ignore
from datetime import timedelta

from opencensus.ext.stackdriver import stats_exporter
from opencensus.stats import aggregation, measure, stats, view
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import \
    TraceContextTextMapPropagator


def get_tracer():
    try:
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
    except Exception:
        return None


def create_elapsed_measure(metrics_name: str):
    m = measure.MeasureInt(f"liualgotrader.{metrics_name}", metrics_name, "ms")
    v = view.View(
        f"liualgotrader.{metrics_name}.distribution",
        "",
        [],
        m,
        aggregation.DistributionAggregation(
            [100, 500, 1000, 2000, 5000, 10000]
        ),
    )
    stats.stats.view_manager.register_view(v)

    return m


def trace_elapsed_metrics(metrics_name: str, value: timedelta):
    if int(value / timedelta(microseconds=1)) < 0:
        return
        # raise ValueError(f"trace_elapsed_metrics can't be negative {value}")

    try:
        trace_elapsed_metrics.measure
    except Exception:
        trace_elapsed_metrics.measure = create_elapsed_measure(metrics_name)

    measure_map = stats.stats.stats_recorder.new_measurement_map()
    measure_map.measure_int_put(
        trace_elapsed_metrics.measure,
        int(value / timedelta(microseconds=1) / 1000),
    )
    measure_map.record()


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
