"""Beginner Java examples for the Java-specific static analysis path."""

JAVA_EXAMPLES = {
    "Hello Java": {
        "id": "java-hello-output",
        "original_code": (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(\"Hello Java\");\n"
            "    }\n"
            "}\n"
        ),
        "expected_diagnosis": "No issue was identified by the available Java checks.",
        "detection_basis": "Static Java rules found no supported beginner-level issue.",
        "corrected_code": None,
        "trusted_tests": [],
        "concept": "Java entry point and output",
        "prevention_tip": "Use the conventional main method and call println with a terminated statement.",
    },
    "Missing semicolon": {
        "id": "java-missing-semicolon",
        "original_code": (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(\"Hello Java\")\n"
            "    }\n"
            "}\n"
        ),
        "expected_diagnosis": "A println statement is missing its terminating semicolon.",
        "detection_basis": "Matched a simple println statement ending without a semicolon.",
        "corrected_code": (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(\"Hello Java\");\n"
            "    }\n"
            "}\n"
        ),
        "trusted_tests": [],
        "concept": "Java statements and semicolons",
        "prevention_tip": "End Java declarations and expression statements with semicolons.",
    },
    "Unmatched brace": {
        "id": "java-unmatched-brace",
        "original_code": "public class Main {\n    public static void main(String[] args) {\n}\n",
        "expected_diagnosis": "An opening class brace has no matching closing brace.",
        "detection_basis": "Delimiter scan found an unmatched opening brace outside comments and strings.",
        "corrected_code": None,
        "trusted_tests": [],
        "concept": "Java blocks and braces",
        "prevention_tip": "Indent nested blocks consistently and pair each opening brace with a closing brace.",
    },
    "Incorrect main capitalization": {
        "id": "java-main-capitalization",
        "original_code": (
            "public class Main {\n"
            "    public static void Main(String[] args) {\n"
            "        System.out.println(\"ready\");\n"
            "    }\n"
            "}\n"
        ),
        "expected_diagnosis": "The conventional Java entry-point method is lowercase main.",
        "detection_basis": "Matched the exact method token Main in a void method declaration.",
        "corrected_code": (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(\"ready\");\n"
            "    }\n"
            "}\n"
        ),
        "trusted_tests": [],
        "concept": "Java case-sensitive identifiers",
        "prevention_tip": "Remember that Java distinguishes uppercase and lowercase letters in names.",
    },
    "println missing parentheses": {
        "id": "java-println-parentheses",
        "original_code": (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println \"ready\";\n"
            "    }\n"
            "}\n"
        ),
        "expected_diagnosis": "The println argument must be enclosed in parentheses.",
        "detection_basis": "Matched a string literal immediately following System.out.println.",
        "corrected_code": (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(\"ready\");\n"
            "    }\n"
            "}\n"
        ),
        "trusted_tests": [],
        "concept": "Java method-call syntax",
        "prevention_tip": "Pass method arguments inside parentheses, then terminate the statement with a semicolon.",
    },
}


def find_java_example_for_source(source: str) -> dict | None:
    """Return a Java fixture only for an exact original sample match."""
    return next(
        (example for example in JAVA_EXAMPLES.values() if source == example["original_code"]),
        None,
    )