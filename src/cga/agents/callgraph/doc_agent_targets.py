
from cga.agents.actions import JsonSchema
from cga.agents.doc.types import Target


def callgraph_targets():
    ft = Target(
        id="function",
        description="function definition",
        schema=JsonSchema(
            type="object",
            properties={
                "file": {
                    "type": "string",
                    "description": "The file where the function is defined."
                },
                "function_name": {
                    "type": "string",
                    "description": "Name of the function defined."
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number of the function definition."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number of the function definition."
                }
            },
            required=["function_name", "start_line", "end_line"]     
        ),
        map_fn=lambda target: {
            "name": target["function_name"],
            "loc": {
                "file": target["file"],
                "start_line": target["start_line"],
                "end_line": target["end_line"]
            }
        }
    )
    return [
        Target(
            id="class",
            description="class definitions",
            schema=JsonSchema(
                type="object",
                properties={
                    "class_name": {
                        "type": "string",
                        "description": "Name of the class."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number of the class definition."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number of the class definition."
                    }
                },
                required=["class_name", "start_line", "end_line"]
            ),
            children=[ft]
        ),
        ft
    ]