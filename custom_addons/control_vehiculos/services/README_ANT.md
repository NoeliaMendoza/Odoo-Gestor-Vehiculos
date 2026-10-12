# Consulta por placa en ANT

Al guardar un vehículo nuevo, se consulta ANT automáticamente si está marcada esa opción. El administrador también puede pulsar **Consultar** después. La consulta completa marca/modelo, año y color, y guarda matrícula, estado de cuenta y citaciones en la pestaña **ANT · Matrícula y citaciones**.

- Fuente: https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_criterio_consulta.jsp
- Es una lectura de la página pública y de sus consultas JSON, no una API con contrato de estabilidad. Si cambia su formato, el lector falla con un mensaje y conserva los datos anteriores.
- `ant_client.py` valida placa, ficha, importes, fechas, cinco estados y paginación. Consulta únicamente el host fijo ANT, con tiempo limitado y sin seguir redirecciones.
- `models/vehicle_ant.py` aplica permisos, completa el vehículo y actualiza citaciones por identificador externo. Espera un minuto entre consultas exitosas a la misma placa.
- `views/ant_views.xml` muestra el botón, la fecha de consulta y la información de solo lectura. `security/ant_security.xml` restringe acceso por grupo y compañía.
- No se extraen documentos personales del titular ni se consulta su historial de puntos. Las citaciones no se asignan al conductor actual ni generan mensajes a terceros.
- La fecha de emisión es la informada por ANT, convertida de Ecuador continental a UTC para Odoo. No equivale necesariamente al momento de la infracción.
- Las citaciones ausentes en una consulta posterior permanecen como antecedente; no se consideran pagadas ni anuladas por esa ausencia.
- `models/ant_records.py` incorpora la matrícula a Documentos y las citaciones a Multas. Actualiza por placa y referencia externa, sin duplicar filas ni reemplazar adjuntos o notas. Una multa ANT conserva los cinco estados oficiales; su monto representa el saldo informado, y sanción, multa y remisión se muestran aparte. Las pagadas y anuladas no se contabilizan como pendientes.
- No se crea un documento si ANT no informa la caducidad. La página no proporciona el archivo de matrícula. Una ficha manual con las mismas fechas se vincula a ANT sólo si hay una única coincidencia.
- Si falla la consulta automática al crear, se guarda el vehículo y un aviso; se permite consultar después. La consulta manual fallida conserva íntegra la última importación.
- La fecha de caducidad se toma literalmente del campo «Fecha de Caducidad» de la matrícula ANT y se guarda en la ficha del vehículo y en Documentos. No se calcula por el último dígito de la placa ni equivale al vencimiento de la revisión técnica.
- La consulta no aporta fotografía, combustible actual, kilometraje, mantenimiento ni firmas; esos datos se registran en el módulo.

La importación exige que todas las páginas estén completas. Se limita a 10 páginas de 50 citaciones por estado para evitar consultas desmedidas; si se excede ese límite se informa el error, sin guardar un resultado parcial.
