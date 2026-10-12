"""Unifica entrega y uso sin perder las fechas de los permisos existentes."""


def migrate(cr, version):
    # Conserva la salida real; para entregas antiguas sin salida usa su fecha de entrega.
    cr.execute("""
        UPDATE control_vehicle_assignment
           SET state = 'delivered',
               checkout_at = COALESCE(checkout_at, delivered_at)
         WHERE state = 'in_use'
            OR (state = 'delivered' AND checkout_at IS NULL)
    """)
