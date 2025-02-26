from vanna.remote import VannaDefault
vn = VannaDefault(model='chinook', api_key='xxx')
# vn.connect_to_sqlite('https://vanna.ai/Chinook.sqlite')
vn.connect_to_sqlite('Chinook.sqlite')
vn.ask('专辑销量最好的3位艺术家的名字是?')

from vanna.flask import VannaFlaskApp
VannaFlaskApp(vn).run()