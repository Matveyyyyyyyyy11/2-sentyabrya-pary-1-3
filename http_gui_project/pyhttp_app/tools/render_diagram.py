"""Рисует диаграмму классов через graphviz (для тех, у кого нет PlantUML)."""
import subprocess

GROUPS = {
    "net": ["Connection«ABC»", "Socket", "BytesConnection", "TcpClient", "TcpServer"],
    "http": ["Url", "Request", "Response", "Parser", "MessageReader", "Serializer"],
    "client": ["HttpClient"],
    "server": ["RequestHandler«ABC»", "RequestObserver«ABC»", "Router", "HttpServer",
               "IndexHandler", "EchoHandler", "TimeHandler", "HeadersHandler",
               "StatusHandler", "LoggingObserver", "QueueObserver"],
    "gui": ["App", "ClientTab", "ServerTab", "SettingsTab", "RequestJob", "HeaderTable",
            "LogTable", "ResponseView"],
}
INHERIT = [("Socket", "Connection«ABC»"), ("BytesConnection", "Connection«ABC»"),
           ("IndexHandler", "RequestHandler«ABC»"), ("EchoHandler", "RequestHandler«ABC»"),
           ("TimeHandler", "RequestHandler«ABC»"), ("HeadersHandler", "RequestHandler«ABC»"),
           ("StatusHandler", "RequestHandler«ABC»"), ("LoggingObserver", "RequestObserver«ABC»"),
           ("QueueObserver", "RequestObserver«ABC»")]
USES = [("MessageReader", "Connection«ABC»"), ("Parser", "MessageReader"),
        ("HttpClient", "TcpClient"), ("HttpClient", "Serializer"),
        ("HttpClient", "MessageReader"), ("HttpClient", "Url"),
        ("HttpServer", "Router"), ("HttpServer", "RequestObserver«ABC»"),
        ("HttpServer", "TcpServer"), ("HttpServer", "MessageReader"),
        ("Router", "RequestHandler«ABC»"), ("Serializer", "Response"),
        ("MessageReader", "Request"), ("App", "ClientTab"), ("App", "ServerTab"),
        ("App", "SettingsTab"), ("ClientTab", "HeaderTable"), ("ClientTab", "ResponseView"),
        ("ClientTab", "RequestJob"), ("RequestJob", "HttpClient"),
        ("ServerTab", "LogTable"), ("ServerTab", "HttpServer"),
        ("ServerTab", "QueueObserver")]


def main() -> None:
    """Сформировать docs/class_diagram.png."""
    lines = ["digraph G {", "rankdir=BT; node [shape=box, fontname=Helvetica, style=filled,"
             " fillcolor=white]; compound=true;"]
    for idx, (name, nodes) in enumerate(GROUPS.items()):
        lines.append(f'subgraph cluster_{idx} {{ label="{name}"; style=rounded;')
        for node in nodes:
            fill = "lightyellow" if "ABC" in node else "white"
            lines.append(f'"{node}" [fillcolor={fill}];')
        lines.append("}")
    for src, dst in INHERIT:
        lines.append(f'"{src}" -> "{dst}" [arrowhead=empty, style=dashed];')
    for src, dst in USES:
        lines.append(f'"{src}" -> "{dst}" [arrowhead=vee, color=gray40];')
    lines.append("}")
    subprocess.run(["dot", "-Tpng", "-Gdpi=110", "-o", "docs/class_diagram.png"],
                   input="\n".join(lines).encode(), check=True)


if __name__ == "__main__":
    main()
