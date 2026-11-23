import copy
from room_items import CATALOG
from PySide6.QtCore import QAbstractListModel,QModelIndex,Qt,QUrl
class DecorationModel(QAbstractListModel):
    Entry=Qt.ItemDataRole.UserRole+1
    def __init__(self,rows,parent=None):super().__init__(parent);self.rows=copy.deepcopy(rows)
    def roleNames(self):return {self.Entry:b'entry'}
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def data(self,index,role):
        if role!=self.Entry or not index.isValid() or not 0<=index.row()<len(self.rows):return None
        row=copy.deepcopy(self.rows[index.row()]);row.update({key:CATALOG[row['kind']].get(key) for key in ('motion','pivotX','pivotY')});row['imageUrl']=QUrl.fromLocalFile(row['image']).toString() if row['image'] else '';return row
    def sync(self,rows):
        ids=[r['id'] for r in rows];old=[r['id'] for r in self.rows]
        if old==ids:
            for i,row in enumerate(rows):
                if row!=self.rows[i]:self.rows[i]=copy.deepcopy(row);self.dataChanged.emit(self.index(i),self.index(i),[self.Entry])
        elif ids[:len(old)]==old:
            self.beginInsertRows(QModelIndex(),len(old),len(rows)-1);self.rows=copy.deepcopy(rows);self.endInsertRows()
        elif len(old)==len(ids)+1 and all(identity in old for identity in ids):
            missing=next(i for i,identity in enumerate(old) if identity not in ids);self.beginRemoveRows(QModelIndex(),missing,missing);self.rows.pop(missing);self.endRemoveRows();self.sync(rows)
        else:self.beginResetModel();self.rows=copy.deepcopy(rows);self.endResetModel()
