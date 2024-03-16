# este script fuerza que los cambios se vean reflejados
# directamente en trytond.
#
# variables exportadas:
# - module_name

[ ! -d "$SRC" ] && die "no se ubica ruta en SRC"

# dependencias minimas
pip3 install psycopg2 proteus==7.0.0 inotify honcho qrcode==6.1 pyshp==2.3.1 shapely==2.0.2
pip3 install trytond-party trytond-company trytond-product trytond-product_image trytond-currency trytond-notification_email

for module in modules/*/; do
 
  pushd "$module"

  # instalar dependencias de tryton desde paquete
  python3 setup.py install

  # usamos enlace al paquete
  python3 setup.py develop

  # instalar modulo
  trytond_modules_path=`pip3 show trytond | grep Location | sed -nr 's/Location: +//gp'`/trytond/modules
  module_name=`cat "setup.py"  | fgrep -A 1 [trytond.modules] | sed 1d | cut -d '=' -f 1 | tr -d ' \n'`
  [ ! -d "$trytond_modules_path" ] && die "fallo al ubicar ruta de modulos de trytond"
  ln -sf "$SRC/$module" "$trytond_modules_path/$module_name"
  rm -rf "$SRC/$module/$module_name"

  popd

done

trytond_path=`pip3 show trytond | grep Location | sed -nr 's/Location: +//gp'`/trytond

if [ -d "locale_custom" ]; then
    cp -f "locale_custom/ir/pt.po" "$trytond_path/ir/locale/"
fi
