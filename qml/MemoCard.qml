import QtQuick
import QtQuick.Controls

WidgetFrame {
    id: root
    objectName: "memoCard"
    widgetKey: "memo"
    title: "메모"
    width: 360
    height: 260

    property bool editing: false
    property bool composerOpen: false
    property bool available: true
    readonly property int selectedTask: bridge.state.selectedTask === undefined ? -1 : bridge.state.selectedTask

    function beginNoteEdit() {
        if (!available || selectedTask >= 0) return
        editing = true
        bridge.setInputActive(true)
        Qt.callLater(function() { noteEditor.forceActiveFocus() })
    }

    function endNoteEdit() {
        if (!editing) return
        Qt.inputMethod.commit()
        bridge.setMemo(noteEditor.text)
        editing = false
        noteEditor.focus = false
        bridge.setInputActive(false)
    }

    function openTaskComposer() {
        if (!available) return
        editing = false
        composerOpen = true
        taskTitle.text = ""
        taskDetail.text = ""
        bridge.setInputActive(true)
        Qt.callLater(function() { taskTitle.forceActiveFocus() })
    }

    function closeTaskComposer() {
        composerOpen = false
        taskTitle.focus = false
        taskDetail.focus = false
        bridge.clearTaskAttachments()
        bridge.setInputActive(false)
    }

    function saveTask() {
        if (taskTitle.text.trim().length === 0) {
            taskTitle.forceActiveFocus()
            return
        }
        bridge.addTask(taskTitle.text, taskDetail.text)
        closeTaskComposer()
    }

    StyledCard {
        id: paper
        anchors.left: parent.left
        anchors.top: parent.top
        width: 292
        height: 260
        fill: root.cardPalette.surface
        stroke: "#58ffffff"
        focused: false
        rounding: 22
    }

    Text {
        x: 20
        y: 18
        text: "메모"
        font.family: bridge.uiFont
        font.pixelSize: 16
        font.weight: Font.DemiBold
        color: root.cardPalette.ink
    }

    IconButton {
        id: taskActionButton
        objectName: "memoEditButton"
        x: 242
        y: 8
        width: 38
        height: 38
        icon: root.selectedTask >= 0 ? "trash" : "edit"
        label: root.selectedTask >= 0 ? "선택한 할 일 삭제" : "할 일 추가"
        ink: root.cardPalette.ink
        onClicked: root.selectedTask >= 0 ? bridge.deleteSelectedTask() : root.openTaskComposer()
    }

    // The memo remains a single, quiet writing surface. Clicking it enters edit mode.
    Item {
        x: 18
        y: 54
        width: 256
        height: 188
        visible: !root.composerOpen

        TextArea {
            id: noteEditor
            objectName: "memoEditor"
            anchors.fill: parent
            text: bridge.memo
            readOnly: !root.editing || root.selectedTask >= 0
            selectByMouse: root.editing
            wrapMode: TextEdit.Wrap
            placeholderText: "눌러서 메모 입력"
            placeholderTextColor: root.cardPalette.muted
            color: root.cardPalette.ink
            font.family: bridge.uiFont
            font.pixelSize: 14
            padding: 3
            background: null
            visible: root.selectedTask < 0
            onTextChanged: if (root.editing) bridge.setMemo(text)
            onActiveFocusChanged: if (root.editing && !activeFocus) root.endNoteEdit()
            Keys.onEscapePressed: root.endNoteEdit()
            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Return && (event.modifiers & Qt.ControlModifier)) {
                    root.endNoteEdit()
                    event.accepted = true
                }
            }
        }

        MouseArea {
            anchors.fill: noteEditor
            visible: root.selectedTask < 0 && !root.editing
            cursorShape: Qt.IBeamCursor
            onClicked: root.beginNoteEdit()
        }

        Column {
            anchors.fill: parent
            visible: root.selectedTask >= 0
            spacing: 9

            Row {
                width: parent.width
                height: 30
                spacing: 4

                Text {
                    width: parent.width - 36
                    text: root.selectedTask >= 0 ? ((bridge.state.tasks[root.selectedTask] || {}).title || "") : ""
                    font.family: bridge.uiFont
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    color: root.cardPalette.ink
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }

                IconButton {
                    width: 30
                    height: 28
                    icon: "check"
                    label: (bridge.state.tasks[root.selectedTask] || {}).done ? "완료 취소" : "완료 표시"
                    ink: root.cardPalette.accent
                    selected: !!(bridge.state.tasks[root.selectedTask] || {}).done
                    onClicked: bridge.toggleTask(root.selectedTask)
                }
            }

            Flickable {
                width: parent.width
                height: parent.height - 58
                clip: true
                contentHeight: taskDetailText.implicitHeight

                Text {
                    id: taskDetailText
                    width: parent.width
                    text: root.selectedTask >= 0 ? ((bridge.state.tasks[root.selectedTask] || {}).detail || "상세 내용이 없습니다.") : ""
                    font.family: bridge.uiFont
                    font.pixelSize: 13
                    color: root.cardPalette.muted
                    wrapMode: Text.WordWrap
                }
            }

            Row {
                spacing: 5
                visible: root.selectedTask >= 0 && ((bridge.state.tasks[root.selectedTask] || {}).attachments || []).length > 0

                Text {
                    text: "첨부"
                    font.family: bridge.uiFont
                    font.pixelSize: 10
                    color: root.cardPalette.muted
                }

                Repeater {
                    model: root.selectedTask >= 0 ? ((bridge.state.tasks[root.selectedTask] || {}).attachments || []) : []
                    Text {
                        required property int index
                        required property string modelData
                        text: "파일 " + (index + 1)
                        font.family: bridge.uiFont
                        font.pixelSize: 10
                        color: root.cardPalette.accent
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: bridge.openTaskAttachment(root.selectedTask, index)
                        }
                    }
                }
            }
        }
    }

    // Compact glass composer with bespoke actions instead of native Qt buttons.
    Rectangle {
        id: composer
        x: 12
        y: 50
        width: 268
        height: 198
        visible: root.composerOpen
        radius: 18
        antialiasing: true
        color: root.cardPalette.dark ? "#e9253037" : "#eaf4f7fa"
        border.width: 1
        border.color: root.cardPalette.dark ? "#42ffffff" : "#a6ffffff"

        Rectangle {
            x: 14
            y: 0
            width: 54
            height: 2
            radius: 1
            color: root.cardPalette.accent
            opacity: 0.55
        }

        Column {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 7

            TextField {
                id: taskTitle
                width: parent.width
                height: 34
                placeholderText: "할 일 제목"
                placeholderTextColor: root.cardPalette.muted
                selectByMouse: true
                leftPadding: 12
                rightPadding: 12
                font.family: bridge.uiFont
                font.pixelSize: 13
                color: root.cardPalette.ink
                background: Rectangle {
                    radius: 10
                    color: root.cardPalette.dark ? "#48202a31" : "#dfffffff"
                    border.width: taskTitle.activeFocus ? 1.2 : 1
                    border.color: taskTitle.activeFocus ? "#82aabd" : "#4affffff"
                    Behavior on border.color { ColorAnimation { duration: bridge.state.motion ? 140 : 0 } }
                }
            }

            TextArea {
                id: taskDetail
                width: parent.width
                height: 86
                placeholderText: "상세 내용을 적어주세요"
                placeholderTextColor: root.cardPalette.muted
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                padding: 11
                font.family: bridge.uiFont
                font.pixelSize: 12
                color: root.cardPalette.ink
                background: Rectangle {
                    radius: 10
                    color: root.cardPalette.dark ? "#48202a31" : "#dfffffff"
                    border.width: taskDetail.activeFocus ? 1.2 : 1
                    border.color: taskDetail.activeFocus ? "#82aabd" : "#4affffff"
                    Behavior on border.color { ColorAnimation { duration: bridge.state.motion ? 140 : 0 } }
                }
            }

            Item {
                width: parent.width
                height: 32

                Row {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 5

                    IconButton {
                        width: 32
                        height: 32
                        icon: "folder"
                        label: "파일 첨부"
                        ink: root.cardPalette.ink
                        fill: root.cardPalette.dark ? "#20ffffff" : "#8affffff"
                        circle: false
                        onClicked: bridge.chooseTaskAttachments()
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: bridge.pendingTaskAttachmentCount > 0 ? "첨부 " + bridge.pendingTaskAttachmentCount + "개" : "파일 추가"
                        font.family: bridge.uiFont
                        font.pixelSize: 10
                        color: root.cardPalette.muted
                    }
                }

                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6

                    Rectangle {
                        id: cancelAction
                        width: 54
                        height: 30
                        radius: 10
                        color: cancelMouse.pressed ? "#20a5b9c5" : cancelMouse.containsMouse ? "#18a5b9c5" : "transparent"
                        border.width: 1
                        border.color: root.cardPalette.dark ? "#36ffffff" : "#55ffffff"
                        scale: cancelMouse.pressed ? 0.96 : 1
                        Behavior on color { ColorAnimation { duration: bridge.state.motion ? 120 : 0 } }
                        Behavior on scale { NumberAnimation { duration: bridge.state.motion ? 120 : 0; easing.type: Easing.OutCubic } }
                        Accessible.role: Accessible.Button
                        Accessible.name: "취소"
                        Text {
                            anchors.centerIn: parent
                            text: "취소"
                            font.family: bridge.uiFont
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: root.cardPalette.ink
                        }
                        MouseArea {
                            id: cancelMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.closeTaskComposer()
                        }
                    }

                    Rectangle {
                        id: saveAction
                        width: 62
                        height: 30
                        radius: 10
                        color: saveMouse.pressed ? "#587f96" : saveMouse.containsMouse ? "#83abc0" : "#739bb3"
                        border.width: 1
                        border.color: "#44ffffff"
                        scale: saveMouse.pressed ? 0.96 : 1
                        Behavior on color { ColorAnimation { duration: bridge.state.motion ? 120 : 0 } }
                        Behavior on scale { NumberAnimation { duration: bridge.state.motion ? 120 : 0; easing.type: Easing.OutCubic } }
                        Accessible.role: Accessible.Button
                        Accessible.name: "저장"
                        Row {
                            anchors.centerIn: parent
                            spacing: 4
                            Icon {
                                name: "check"
                                ink: "#f8fbfd"
                                width: 13
                                height: 13
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: "저장"
                                font.family: bridge.uiFont
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                                color: "#f8fbfd"
                            }
                        }
                        MouseArea {
                            id: saveMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.saveTask()
                        }
                    }
                }
            }
        }

        DropArea {
            anchors.fill: parent
            onDropped: function(drop) {
                if (drop.hasUrls) {
                    bridge.addTaskAttachments(drop.urls.map(function(url) { return url.toString() }))
                    drop.acceptProposedAction()
                }
            }
        }
    }

    // Rectangular paper tabs attach directly to the memo's right edge.
    Flickable {
        x: 291
        y: 54
        width: 69
        height: 202
        clip: true
        contentHeight: Math.max(height, bridge.state.tasks.length * 30)

        Column {
            width: 69
            spacing: 3

            Repeater {
                model: bridge.state.tasks

                Item {
                    required property var modelData
                    required property int index
                    width: 69
                    height: 27
                    property int tabWidth: Math.max(48, Math.min(69, 49 + ((index * 17 + String(modelData.title || modelData.text || "").length * 9) % 21)))
                    property var tabColors: ["#dcebe4", "#eee1dc", "#e2e6f1", "#f0ead6", "#dce9ef", "#ece2ed"]

                    Rectangle {
                        x: 0
                        y: 2
                        width: parent.tabWidth
                        height: 25
                        color: "#160b1a20"
                    }

                    Rectangle {
                        x: 0
                        y: 0
                        width: parent.tabWidth
                        height: 25
                        color: root.selectedTask === parent.index ? "#eaf5f8fa" : parent.tabColors[parent.index % parent.tabColors.length]
                        opacity: root.selectedTask === parent.index ? 0.98 : 0.88
                        scale: tabMouse.pressed ? 0.985 : tabMouse.containsMouse ? 1.012 : 1
                        Behavior on scale { NumberAnimation { duration: bridge.state.motion ? 130 : 0; easing.type: Easing.OutCubic } }
                        border.width: root.selectedTask === parent.index ? 1 : 0
                        border.color: "#a6ffffff"

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 7
                            anchors.right: parent.right
                            anchors.rightMargin: 5
                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.parent.modelData.title || parent.parent.modelData.text || "할 일"
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignLeft
                            font.family: bridge.uiFont
                            font.pixelSize: 9
                            font.weight: root.selectedTask === parent.parent.index ? Font.DemiBold : Font.Medium
                            font.strikeout: parent.parent.modelData.done
                            color: "#35464d"
                        }

                        MouseArea {
                            id: tabMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.editing = false
                                root.composerOpen = false
                                bridge.setInputActive(false)
                                bridge.selectTask(root.selectedTask === parent.parent.index ? -1 : parent.parent.index)
                            }
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: bridge
        function onMemoInputRequested() { if (root.available) root.beginNoteEdit() }
        function onInputChanged() {
            if (!bridge.inputActive && root.editing) root.endNoteEdit()
            if (!bridge.inputActive && root.composerOpen) root.closeTaskComposer()
        }
        function onMemoChanged() {
            if (!root.editing && noteEditor.text !== bridge.memo) noteEditor.text = bridge.memo
        }
    }
}
