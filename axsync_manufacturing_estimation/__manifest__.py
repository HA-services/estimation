{
    'name': 'Axsync Manufacturing Estimation',
    'category': "Manufacturing",
    'license':'LGPL-3',
    'summary': 'Smart Raw Material Check and Manufacturing Estimation',
    'author': 'Axsync Global',
    'depends': ['base', 'product', 'sale_management', 'mrp'],
    'data': [
            "security/ir.model.access.csv",
            "data/data.xml",
            "views/insabhi_manufacturing_estimation.xml",
            ],
    'images': ['static/description/one.png'],
    'installable':True,
    'auto_install':False,
    'application':True,
}