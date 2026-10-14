from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsLineItem, QMenu

COLORS = {'Host':'#62dbc3','Service':'#74a9ff','Finding':'#ffb86b','Credential':'#ce9dff','Access':'#f57894','Note':'#aab9cb'}

class Node(QGraphicsRectItem):
    def __init__(self, row, moved):
        super().__init__(0,0,220,76)
        self.row = dict(row)
        self.moved = moved
        self.edges = []
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setBrush(QBrush(QColor('#1b2738')))
        pen = QPen(QColor(COLORS[row['kind']]),2)
        if row['status']=='hypothesis': pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        title=QGraphicsSimpleTextItem(row['kind'].upper()+' · '+row['status'],self)
        title.setBrush(QColor(COLORS[row['kind']]))
        title.setPos(12,10)
        label=QGraphicsSimpleTextItem(row['label'][:27]+('…' if len(row['label'])>27 else ''),self)
        label.setBrush(QColor('#eef4ff')); label.setPos(12,36)
        self.setToolTip(row['label']+'\n'+row['detail'])
        self.setPos(row['x'],row['y'])
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges: edge.update_line()
        return super().itemChange(change,value)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.moved(self.row['id'],self.pos().x(),self.pos().y())

class Edge(QGraphicsLineItem):
    def __init__(self, source, target, label):
        super().__init__()
        self.source,self.target=source,target
        source.edges.append(self); target.edges.append(self)
        self.setPen(QPen(QColor('#51627d'),1.5))
        self.setZValue(-1); self.setToolTip(label)
        self.caption=QGraphicsSimpleTextItem(label,self)
        self.caption.setBrush(QColor('#93a4ba'))
        self.update_line()
    def update_line(self):
        from PySide6.QtCore import QLineF
        a=self.source.pos()+QPointF(110,38); b=self.target.pos()+QPointF(110,38)
        self.setLine(QLineF(a,b))
        self.caption.setPos((a+b)/2)

class Graph(QGraphicsView):
    selected = Signal(object)
    create_requested = Signal()
    link_requested = Signal()
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store=store
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor('#111925'))
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.nodes={}
        self.scene().selectionChanged.connect(self.selection)
    def selection(self):
        items=self.scene().selectedItems()
        self.selected.emit(items[0].row if items and isinstance(items[0],Node) else None)
    def load(self, project, search='', offset=0, kind='All'):
        self.scene().clear(); self.nodes={}
        rows=self.store.nodes(project,search,offset)
        for row in rows:
            if kind!='All' and row['kind']!=kind: continue
            node=Node(row,self.store.position); self.scene().addItem(node); self.nodes[row['id']]=node
        for row in self.store.edges(project,list(self.nodes)):
            self.scene().addItem(Edge(self.nodes[row['source']],self.nodes[row['target']],row['label']))
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-300,-300,300,300))
    def layout_nodes(self):
        groups={kind:[] for kind in COLORS}
        for node in self.nodes.values(): groups[node.row['kind']].append(node)
        for column, nodes in enumerate(groups.values()):
            for index,node in enumerate(nodes):
                node.setPos(column*290,index*115)
                self.store.position(node.row['id'],node.pos().x(),node.pos().y())
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-300,-300,300,300))
        self.fit()
    def fit(self):
        bounds=self.scene().itemsBoundingRect()
        if not bounds.isEmpty(): self.fitInView(bounds.adjusted(-40,-40,40,40),Qt.KeepAspectRatio)
    def wheelEvent(self,event):
        factor=1.15 if event.angleDelta().y()>0 else 1/1.15
        scale=self.transform().m11()*factor
        if .08<scale<4:
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.scale(factor,factor)
        event.accept()
    def mousePressEvent(self,event):
        if event.button()==Qt.MiddleButton:
            self.pan_origin=event.position(); self.setCursor(Qt.ClosedHandCursor); event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.MiddleButton and hasattr(self,'pan_origin'):
            delta=event.position()-self.pan_origin; self.pan_origin=event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-int(delta.y()))
            event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MiddleButton: self.unsetCursor(); event.accept(); return
        super().mouseReleaseEvent(event)
    def contextMenuEvent(self,event):
        menu=QMenu(self)
        menu.addAction('Add node',self.create_requested.emit)
        menu.addAction('Link selected nodes',self.link_requested.emit)
        menu.addAction('Arrange map',self.layout_nodes)
        menu.addAction('Fit map',self.fit)
        menu.exec(event.globalPos())
