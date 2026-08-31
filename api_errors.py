"""Public errors without leaking provider or database internals."""
import json
import logging
import uuid


class SafeRequestError(ValueError):
    """Only application-authored validation messages may reach the user."""


def validate_chat(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list):
        raise ValueError('Se requiere una lista de mensajes.')
    messages = payload['messages']
    if not messages or len(messages) > 500:
        raise ValueError('Envía entre 1 y 500 mensajes por consulta.')
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant'):
            raise ValueError('Rol de mensaje no válido.')
        if not isinstance(message.get('content'), str) or len(message['content']) > 100000:
            raise ValueError('Contenido del mensaje no válido o demasiado largo.')
    if messages[-1]['role'] != 'user' or not messages[-1]['content'].strip():
        raise ValueError('Escribe un mensaje antes de enviar.')
    return messages


def public_error(exc):
    reference = uuid.uuid4().hex[:12]
    logging.getLogger('nexo_bi').exception('Fallo de consulta %s', reference)
    name = type(exc).__name__
    if isinstance(exc, SafeRequestError):
        status, code, message = 400, 'invalid_request', str(exc)
    elif isinstance(exc, (ValueError, json.JSONDecodeError)):
        status, code, message = 400, 'invalid_request', 'La solicitud contiene datos inválidos. Revisa el mensaje, las fechas y los filtros.'
    elif name == 'RateLimitError':
        status, code, message = 429, 'provider_limit', 'El proveedor de IA rechazó la solicitud por un límite. Puede ser temporal o de cuota; revisa el detalle en el servidor.'
    elif name in ('AuthenticationError', 'PermissionDeniedError'):
        status, code, message = 503, 'provider_configuration', 'La IA no tiene acceso autorizado. Revisa su configuración en el servidor.'
    elif isinstance(exc, TimeoutError) or name == 'APITimeoutError':
        status, code, message = 504, 'timeout', 'La consulta tardó demasiado. Puedes probar un periodo más corto.'
    elif name in ('OperationalError', 'APIConnectionError', 'ConnectionError'):
        status, code, message = 503, 'connection', 'No se pudo conectar con uno de los servicios necesarios. Comprueba la conexión y el servidor.'
    else:
        status, code, message = 500, 'internal_error', 'No se pudo completar la consulta por un error interno.'
    return {'ok': False, 'error': message, 'code': code, 'reference': reference}, status
