

from vanna.remote import VannaDefault
vn = VannaDefault(model='sjx_vanna', api_key='xxxxx')

# Connect to your database here
vn.connect_to_mysql(host='localhost', dbname='xianyu_db', user='sgg', password='Zpepc001', port=3306)
# vn.train(question="邮箱为ts@qq.com的用户是?", sql="SELECT username FROM xu_user WHERE email = 'ts@qq.com';")

vn.train(ddl="""
CREATE TABLE `xu_user` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    `username` VARCHAR(255) NOT NULL COMMENT '用户名，用于查询用户信息',
    `password` VARCHAR(255) NOT NULL COMMENT '用户密码',
    `email` VARCHAR(255) NOT NULL COMMENT '用户邮箱，用于查询用户邮箱信息',
    `reset_token` VARCHAR(255) NULL COMMENT '密码重置令牌'
) COMMENT='存储用户信息，包括用户名、邮箱、密码等';
""")
vn.train(ddl="""
CREATE TABLE products (  
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '产品唯一标识',  
    name VARCHAR(255) NOT NULL COMMENT '产品名称',  
    description VARCHAR(255) NULL COMMENT '产品描述',  
    price FLOAT NOT NULL COMMENT '产品价格',  
    user_id INT NOT NULL COMMENT '上传用户的ID',  
    tag VARCHAR(255) NOT NULL COMMENT '产品标签',  
    image VARCHAR(255) NULL COMMENT '产品图片URL',  
    quantity INT NOT NULL COMMENT '产品数量',  
    status VARCHAR(64) NOT NULL COMMENT '产品状态',  
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP NULL COMMENT '上传时间',  
    CONSTRAINT products_ibfk_1 FOREIGN KEY (user_id) REFERENCES xu_user (id)  
) 
  COMMENT='存储产品/商品信息，包括产品名称、产品描述、产品价格';
""")

# vn.ask('邮箱为ts@qq.com的用户是?')
from vanna.flask import VannaFlaskApp
VannaFlaskApp(vn).run()


