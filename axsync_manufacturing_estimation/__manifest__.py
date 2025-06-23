# -*- coding: utf-8 -*-
##############################################################################
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##############################################################################
{
    'name': 'Axsync Manufacturing Estimation',
    'category': "Manufacturing",
    'license':' OPL-1',
    'summary': 'Smart Raw Material Check and Manufacturing Estimation',
    'author': 'Axsync Global',
    'depends': ['base', 'product', 'sale_management', 'mrp', 'purchase'],
    'data': [
            "security/ir.model.access.csv",
            "data/data.xml",
            "views/insabhi_manufacturing_estimation.xml",
            ],

    'installable':True,
    'auto_install':False,
    'application':True,
    'currency':'USD',
    'price':'59.00',
    'images':'[/static/description/BANNER.png]'
    
}