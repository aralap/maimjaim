ORDER_STATUS = {
    "draft": "Borrador",
    "confirmed": "Confirmado",
    "fulfilled": "Entregado",
    "cancelled": "Cancelado",
}

PAYMENT_STATUS = {
    "unpaid": "Impago",
    "partial": "Pago parcial",
    "paid": "Pagado",
    "refunded": "Reembolsado",
}

PAYMENT_METHODS = {
    "cash": "Efectivo",
    "transfer": "Transferencia",
    "card": "Tarjeta",
    "mercado_pago": "Mercado Pago",
    "other": "Otro",
}

MOVEMENT_REASONS = {
    "receive": "Ingreso",
    "adjustment": "Ajuste",
    "sale": "Venta",
    "return": "Devolución",
    "reservation": "Reserva",
    "release": "Liberación",
}

ORDER_SOURCE = {
    "manual": "Manual",
    "api": "API",
    "whatsapp": "WhatsApp",
}

USER_ROLES = {
    "admin": "Administrador",
    "staff": "Personal",
}

AUDIT_ACTIONS = {
    "product.create": "Producto creado",
    "product.update": "Producto actualizado",
    "product.deactivate": "Producto desactivado",
    "product.activate": "Producto reactivado",
    "product.variant.create": "Variante agregada",
    "product.variant.update": "Precio/costo actualizado",
    "catalog.seed": "Catálogo cargado",
    "inventory.receive": "Ingreso de stock",
    "inventory.adjust": "Ajuste de stock",
    "order.create": "Pedido creado",
    "order.confirm": "Pedido confirmado",
    "order.fulfill": "Pedido entregado",
    "order.cancel": "Pedido cancelado",
    "order.payment.update": "Pago actualizado",
    "order.delivery.update": "Entrega actualizada",
    "client.create": "Cliente creado",
    "client.update": "Cliente actualizado",
    "auth.login": "Inicio de sesión",
    "auth.logout": "Cierre de sesión",
    "user.approve": "Usuario habilitado",
    "user.revoke": "Usuario deshabilitado",
    "user.role.update": "Rol de usuario actualizado",
}

ENTITY_TYPES = {
    "product": "Producto",
    "inventory": "Inventario",
    "order": "Pedido",
    "client": "Cliente",
    "catalog": "Catálogo",
    "auth": "Autenticación",
    "user": "Usuario",
}

PAYMENT_METHOD_CHOICES = list(PAYMENT_METHODS.items())


def label(mapping: dict, key: str | None) -> str:
    if not key:
        return "—"
    return mapping.get(key, key.replace("_", " ").capitalize())
