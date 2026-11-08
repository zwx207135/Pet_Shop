"""业务层（成员B）。

页面层只与 service 交互；service 负责调用 DAO、组织事务边界与业务规则，
把表单字符串转换成 DAO 需要的类型。DAO 只抛出 ``DAOError``。
"""
