from flask import Flask, jsonify, request, render_template
import heapq, json, os

app = Flask(__name__, template_folder="templates")

DATA_FILE = "data.json"

# ---------------- Models ---------------- #
class DepartmentNode:
    def __init__(self, name, head="", employees=0, budget=0, perf=0):
        self.name = name
        self.head = head
        self.employees = employees
        self.budget = budget
        self.perf = perf
        self.children = []

class DepartmentHierarchy:
    def __init__(self):
        self.root = None
        self.nodes = {}  # name -> node

    def add(self, name, parent=None, head="", employees=0, budget=0, perf=0):
        if name in self.nodes:
            return False
        new_node = DepartmentNode(name, head, employees, budget, perf)
        self.nodes[name] = new_node
        if not parent:
            if not self.root:
                self.root = new_node
        else:
            parent_node = self.nodes.get(parent)
            if parent_node:
                parent_node.children.append(new_node)
            else:
                # if parent missing, attach at root
                if not self.root:
                    self.root = new_node
        return True

    def find_parent_and_remove(self, name):
        for node in self.nodes.values():
            node.children = [c for c in node.children if c.name != name]

    def delete(self, name):
        if name not in self.nodes:
            return False
        # prevent deleting root easily — allow but reset root if it is deleted
        if self.root and self.root.name == name:
            self.root = None
        # remove from parent's children
        self.find_parent_and_remove(name)
        # recursively delete subtree nodes
        to_delete = [name]
        i = 0
        while i < len(to_delete):
            cur = to_delete[i]
            node = self.nodes.get(cur)
            if node:
                for c in node.children:
                    to_delete.append(c.name)
            i += 1
        for n in to_delete:
            if n in self.nodes:
                del self.nodes[n]
        return True

    def edit(self, name, new_name=None, head=None, employees=None, budget=None, perf=None, parent=None):
        if name not in self.nodes:
            return False
        node = self.nodes[name]
        # update meta
        if head is not None: node.head = head
        if employees is not None: node.employees = int(employees)
        if budget is not None: node.budget = float(budget)
        if perf is not None: node.perf = float(perf)
        # rename (careful)
        if new_name and new_name != name:
            if new_name in self.nodes:
                return False
            # move mapping
            node.name = new_name
            self.nodes[new_name] = node
            del self.nodes[name]
            # update child references in parent lists
            for n in self.nodes.values():
                for c in n.children:
                    if c.name == name:
                        c.name = new_name
        # parent reassign
        if parent is not None:
            # remove from existing parents
            self.find_parent_and_remove(node.name)
            if parent == "" or parent not in self.nodes:
                # make root if no parent and no root exists
                if not self.root:
                    self.root = node
            else:
                self.nodes[parent].children.append(node)
        return True

    def to_dict(self, node=None):
        if node is None:
            node = self.root
        if not node:
            return {}
        return {
            "name": node.name,
            "head": node.head,
            "employees": node.employees,
            "budget": node.budget,
            "perf": node.perf,
            "children": [self.to_dict(c) for c in node.children]
        }

    def get_flat_meta(self):
        # returns list of metadata for charts/search
        out = []
        for name, node in self.nodes.items():
            out.append({
                "name": node.name,
                "head": node.head,
                "employees": node.employees,
                "budget": node.budget,
                "perf": node.perf
            })
        return out

# ---------------- Heap wrapper ---------------- #
class DepartmentHeap:
    def __init__(self):
        self.heap = []  # list of (priority, name)

    def add(self, priority, name):
        heapq.heappush(self.heap, (priority, name))

    def remove(self, name):
        self.heap = [(p, n) for p, n in self.heap if n != name]
        heapq.heapify(self.heap)

    def edit_priority(self, name, new_priority):
        self.remove(name)
        self.add(new_priority, name)

    def get_all(self):
        return sorted(self.heap)

# ---------------- Persistence & preload ---------------- #
hierarchy = DepartmentHierarchy()
priority_heap = DepartmentHeap()

def preload_sample_data():
    # Manually define nodes with metadata and priorities
    sample = [
        # (name, parent, head, employees, budget, perf, priority)
        ("Head Office", None, "R. Singh", 120, 1500000, 9.2, 1),
        ("Finance", "Head Office", "S. Patel", 18, 250000, 8.4, 2),
        ("Accounts Payable", "Finance", "G. Rao", 6, 60000, 7.8, 5),
        ("Accounts Receivable", "Finance", "N. Iyer", 6, 70000, 8.0, 6),
        ("HR", "Head Office", "M. Khan", 10, 150000, 8.1, 3),
        ("Recruitment", "HR", "A. Verma", 4, 40000, 7.5, 7),
        ("Employee Relations", "HR", "L. Das", 6, 50000, 8.2, 8),
        ("Engineering", "Head Office", "K. Mehta", 60, 900000, 9.0, 4),
        ("Software", "Engineering", "D. Rao", 35, 600000, 9.3, 9),
        ("AI Team", "Software", "P. Sharma", 12, 300000, 9.6, 11),
        ("Testing", "Software", "R. Nair", 8, 80000, 8.7, 12),
        ("Hardware", "Engineering", "T. Bose", 25, 300000, 8.8, 10),
        ("Manufacturing", "Hardware", "V. Gupta", 20, 250000, 8.5, 13)
    ]
    for name, parent, head, emp, bud, perf, pr in sample:
        hierarchy.add(name, parent, head, emp, bud, perf)
        priority_heap.add(pr, name)
    save_data()

def save_data():
    data = {
        "hierarchy": hierarchy.to_dict(),
        "heap": priority_heap.get_all()
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
            # build nodes recursively
            def build(node, parent=None):
                if not node:
                    return
                name = node.get("name")
                head = node.get("head", "")
                employees = node.get("employees", 0)
                budget = node.get("budget", 0)
                perf = node.get("perf", 0)
                hierarchy.add(name, parent, head, employees, budget, perf)
                for c in node.get("children", []):
                    build(c, name)
            build(data.get("hierarchy"))
            for p, n in data.get("heap", []):
                priority_heap.add(p, n)
    else:
        preload_sample_data()

load_data()

# ---------------- Routes ---------------- #
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/hierarchy")
def get_hierarchy():
    return jsonify(hierarchy.to_dict())

@app.route("/heap")
def get_heap():
    return jsonify(priority_heap.get_all())

@app.route("/meta")
def get_meta():
    # flat metadata for charts/search
    return jsonify(hierarchy.get_flat_meta())

@app.route("/add", methods=["POST"])
def add_dept():
    d = request.json
    name = d.get("name")
    parent = d.get("parent") or None
    head = d.get("head", "")
    employees = int(d.get("employees", 0))
    budget = float(d.get("budget", 0))
    perf = float(d.get("perf", 0))
    priority = int(d.get("priority", 999))
    if not name:
        return jsonify({"error": "Missing name"}), 400
    ok = hierarchy.add(name, parent, head, employees, budget, perf)
    if not ok:
        return jsonify({"error": "Department exists"}), 400
    priority_heap.add(priority, name)
    save_data()
    return jsonify({"message": "Added"})

@app.route("/edit", methods=["POST"])
def edit_dept():
    d = request.json
    name = d.get("name")
    if not name:
        return jsonify({"error": "Missing name"}), 400
    new_name = d.get("new_name")
    head = d.get("head")
    employees = d.get("employees")
    budget = d.get("budget")
    perf = d.get("perf")
    parent = d.get("parent") if "parent" in d else None
    priority = d.get("priority")
    ok = hierarchy.edit(name, new_name, head, employees, budget, perf, parent)
    if not ok:
        return jsonify({"error": "Edit failed (name conflict?)"}), 400
    if priority is not None:
        priority_heap.edit_priority(new_name or name, int(priority))
    save_data()
    return jsonify({"message": "Edited"})

@app.route("/delete", methods=["POST"])
def delete_dept():
    d = request.json
    name = d.get("name")
    if not name:
        return jsonify({"error": "Missing name"}), 400
    ok = hierarchy.delete(name)
    if not ok:
        return jsonify({"error": "Delete failed"}), 400
    priority_heap.remove(name)
    save_data()
    return jsonify({"message": "Deleted"})

@app.route("/stats")
def stats():
    # prepare datasets: employees per dept, budget per dept
    meta = hierarchy.get_flat_meta()
    names = [m["name"] for m in meta]
    employees = [m["employees"] for m in meta]
    budgets = [m["budget"] for m in meta]
    perf = [m["perf"] for m in meta]
    return jsonify({
        "names": names,
        "employees": employees,
        "budgets": budgets,
        "perf": perf
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
