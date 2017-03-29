Arroyo
======

Arroyo es un gestor de descargas automático multimedio y multiidioma.

Como funciona
=============

Arroyo extrae los enlaces magnet encontrados en un conjunto de URLs definidos por el usuario, analizandolos y extrayendo información de ellos, y los guarda en una base de datos.

Posteriormente, y en base a una serie de criterios ya definidos por el usuario, selecciona los enlaces correspondientes y continua con su descarga.

Arroyo recuerda que material ha sido descargado ya (o está en proceso) y es consciente de que varios enlaces pueden corresponder a un mismo episodio o pelicula. De este modo evita bajar dos veces el mismo contenido. Así mismo permite seleccionar la calidad o idioma de los contenidos que se desean.

En cierto modo arroyo es un cruce entre SickBeard y Couchpotato añadiendole siendo además multiidioma.

Uso de la linea de comandos
===========================

Importación
-----------
Para que Arroyo sea útil necesita tener información sobre enlaces en su base de datos.

Este proceso se lleva a cabo con el comando 'import'. Un ejemplo:

> $ arroyo import --backend kickass

En este caso estamos importando enlances usando el backend 'kickass' el cual analiza la pagina principal de dicha pagina y extrae la información relevante.

El comando 'import' acepta las siguientes opciones:

  * **--provider <provider>** Especifica el backend a utilizar.
  
  * **-u <uri>, --uri <uri>** Especifica la URI a analizar. Sirve para especificar analizar URLs especificas como las que se obtienen para realizar búsquedas o determinados listados especificos.

  * **-i <entero>, --iterations <entero>** Muchas de las páginas que Arroyo analiza usan paginación, es decir, un listado se extiende a lo largo de varios enlaces o páginas. Usando este parametro Arroyo recorrerá automáticamente el número de páginas que se le indique

  * **-t <tipo>, --type <tipo>** Arroyo analiza los contenidos de forma inteligente detectando el tipo de contenido al que se refieren los enlaces (episodio, pelicula, libro, audio) pero en ocasiones es deseable forzar este tipo. Este parámetro fuerza el tipo para todo el material encontrado.

  * -l <xx-XX>, --language <xx-XX> **De forma analoga al parametro type pero para el idioma del contenido.**

El comando 'import' puede usar el archivo de configuracion para obtener los parámetros anteriores. Para ello se pueden definir una o varias secciones siguendo el siguiente esquema. (Únicamente el parámetro 'backend' es obligatorio)

```
origin:
  nombre:
    provider: kickass
    uri: https://kickass.cd/usearch/category:tv
    type: episode
```

Para que el comando 'import' importe todas las páginas especificadas en las secciones 'source' del archivo de configuración se ha de usar la siguiente linea de comandos:

> $ arroyo import --from-config

Búsqueda
--------

El proceso de búsqueda y descarga automática es muy similar, realmente es el mismo.

Para buscar utilizamos el comando 'search':

> $ arroyo search -f name-glob='*interstellar*'

En este ejemplo hemos buscado todo el material cuyo nombre contenga la palabra "interstellar".

El comando 'search' necesita uno o varios parametros '-f' que definen que filtros se utilzan en la búsqueda. Tras aplicar todos los filtros sumistrados sobre la base de datos mostrará los resultados.

```
[Insertar output]
```

Uniendo varios filtros podemos definir nuestras búsquedas automáticas:

> $ arroyo search -f type=episode -f series='the big bang theory' -f language='spa-es' -f quality=720p

El comando 'search' muestra únicamente los resultados correspondientes a material que aún no se ha puesto descargar, descartando todo aquel material que ya esté descartado. Si queremos mostrar todos los resultados podemos añadir el parámetro '-a' o '--all' a la línea de comandos:

> $ arroyo search -f type=episode -f series='the big bang theory' -f language='spa-es' -f quality=720p --all

Opcionalmente el comando 'search' se puede usar de forma simplificada:

> $ arroyo search game of thrones s02e03

Que realmente se traduce como:

> $ arroyo search -f name-glob='*game*of*thrones*s02e03*'

Descarga
--------

El proceso de descarga es exactamente el mismo que el de busqueda. Simplemente se utiliza el comando 'download' en lugar de 'search':

> $ arroyo search -f type=episode -f series='the big bang theory' -f language='spa-es' -f quality=720p

Pasaría a ser:

> $ arroyo download -f type=episode -f series='the big bang theory' -f language='spa-es' -f quality=720p

Del mismo modo que el comando 'import' puede usar el archivo de configuración, el comando 'download' puede usar una o varias consultas definidas en el archivo de configuración usando el siguiente esquema de sección:

```
query:
  the big bang (es) 720p:
    type: episode
    series: the big bang theory
    quality: 720p
    language: spa-es
```

Para que el comando 'download' aplique estas consultas y comience a descargar el material correspondiente se ha de usar la siguiente linea de comandos:

> $ arroyo download --from-config

Adicionalmente el comando 'download' permite gestionar las descargas en curso usando los siguientes parámetros:

  * **-a, --add**
  * **-r, --remove**
  * **-l, --list**

Automatizando el proceso
------------------------

Utilizar la combinacion de los anteriores comandos puede resultar pesado por ello arroyo incorpora una caracteristica llamada cron. Esta caracteristica permite que las tareas periodicas como importar, consultar la base de datos y añadir las descargas se realicen de forma automatica.

Para utilizarla se han de definir previamente las secciones 'origin' y 'query' que se deseen en el archivo de configuración. Con esto hecho solamente se deberá ejecutar el siguiente comando que automaticamente realizará todas las tareas anteriormente descritas.

> $ arroyo cron -a


Hacking
=======

Para explicar como funciona se han de explicar los conceptos básicos en los que se basa Arroyo:

  * **Source**: Un source es básicamente un enlace magnet. Además contiene otro tipo de información como el tipo de archivo (episodio, pelicula, libro, etc…) al que pertenece y el idioma del mismo
  * **Analizadores**: Son las piezas encargadas de extraer los Sources (o enlaces magnet) de una determinada URL. Adicionalmente pueden determinar el idioma o tipo de estos Sources si procede
  * **Origin**: Un origin (u origen) se define como: una URL, un analizador para extraer los Sources que contiene, el numero de iteraciones y el idioma y tipo por defecto para los Sources encontrados
