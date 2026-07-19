import os
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

def setup_observability():
    # Only setup once
    if getattr(setup_observability, "_setup_done", False):
        return
    setup_observability._setup_done = True

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not otlp_endpoint:
        logger.info("OpenTelemetry exporter disabled because OTEL_EXPORTER_OTLP_ENDPOINT is not set.")
        return
    
    # Initialize OTel Providers
    resource = Resource.create({
        "service.name": "tablesys-backend",
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("ENVIRONMENT", "development")
    })
    
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/metrics"))]
    )
    metrics.set_meter_provider(meter_provider)
    
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces"))
    )

setup_observability()

# Create globally accessible meters
api_meter = metrics.get_meter("tablesys.api")
api_request_duration_histogram = api_meter.create_histogram(
    "tablesys.api.request.duration",
    description="Duration of HTTP requests",
    unit="ms"
)
api_request_count_counter = api_meter.create_counter(
    "tablesys.api.request.count",
    description="Number of HTTP requests"
)

db_meter = metrics.get_meter("tablesys.db")
db_query_duration_histogram = db_meter.create_histogram(
    "tablesys.db.query.duration",
    description="Duration of database queries",
    unit="ms"
)

generation_meter = metrics.get_meter("tablesys.generation")
generation_duration_histogram = generation_meter.create_histogram(
    "tablesys.generation.duration",
    description="Duration of timetable generation",
    unit="ms"
)
generation_success_counter = generation_meter.create_counter(
    "tablesys.generation.success",
    description="Successful timetable generations"
)
generation_timeout_counter = generation_meter.create_counter(
    "tablesys.generation.timeout",
    description="Timetable generation timeouts"
)
generation_fallback_counter = generation_meter.create_counter(
    "tablesys.generation.fallback_invoked",
    description="Fallback invoked during generation"
)
generation_variables_histogram = generation_meter.create_histogram(
    "tablesys.generation.variables",
    description="Number of solver variables",
    unit="{variables}"
)

task_meter = metrics.get_meter("tablesys.task")
task_queue_time_histogram = task_meter.create_histogram(
    "tablesys.task.queue_time",
    description="Task queuing time",
    unit="ms"
)
task_processing_time_histogram = task_meter.create_histogram(
    "tablesys.task.processing_time",
    description="Task processing time",
    unit="ms"
)
