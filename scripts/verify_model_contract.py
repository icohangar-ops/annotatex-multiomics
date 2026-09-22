#!/usr/bin/env python3
"""Evidence-matrix script row — Lightning model contract (stdlib-only).

AST-checks the README's ML Model claims against the actual sources: the
6-feature / 128-unit / 10-GO-label architecture, the AdamW + ReduceLROnPlateau
optimizer with early stopping on val loss, 20-pass Monte Carlo dropout
inference, and the DE accuracy/F1 + GO macro-F1 metrics.

Exits 0 when every check passes, 1 otherwise. No network, no third-party
imports.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    line = f"  [{status}] {name}"
    if not cond and detail:
        line += f" -- {detail}"
    print(line)
    if not cond:
        FAILURES.append(name)


def parse(relpath):
    return ast.parse((ROOT / relpath).read_text(encoding="utf-8"))


def find_class(tree, name):
    return next((n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name), None)


def find_method(cls, name):
    return next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name), None)


def default_of(fn, arg_name):
    """Default value of a named arg (ast Constant value) or None."""
    args = fn.args
    all_args = args.posonlyargs + args.args + args.kwonlyargs
    defaults = [None] * (len(all_args) - len(args.defaults)) + args.defaults
    for arg, default in zip(all_args, defaults):
        if arg.arg == arg_name:
            return default.value if isinstance(default, ast.Constant) else None
    return None


def find_assign_call(cls, attr, call_name):
    """Find `self.<attr> = ... <call_name>(...)` in a class body (any method)."""
    for method in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(method):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Attribute) \
                    and node.targets[0].attr == attr and isinstance(node.value, ast.Call) \
                    and isinstance(node.value.func, ast.Attribute) \
                    and node.value.func.attr == call_name:
                return node.value
    return None


def main():
    model_tree = parse("annotatex/models/annotatex.py")

    net = find_class(model_tree, "AnnotateXNetwork")
    check("AnnotateXNetwork class exists", net is not None)
    net_init = find_method(net, "__init__") if net else None
    check("network input_dim defaults to 6",
          net_init is not None and default_of(net_init, "input_dim") == 6)
    check("network hidden_dim defaults to 128",
          net_init is not None and default_of(net_init, "hidden_dim") == 128)
    de_head = find_assign_call(net, "de_head", "Linear") if net else None
    check("binary DE head (hidden -> 1)",
          de_head is not None and len(de_head.args) == 2
          and isinstance(de_head.args[1], ast.Constant) and de_head.args[1].value == 1)
    go_head = find_assign_call(net, "go_head", "Linear") if net else None
    check("GO head sized by n_go_terms",
          go_head is not None and len(go_head.args) == 2
          and isinstance(go_head.args[1], ast.Name) and go_head.args[1].id == "n_go_terms")
    encoder_has_batchnorm = False
    if net:
        encoder = find_assign_call(net, "encoder", "Sequential")
        encoder_has_batchnorm = encoder is not None and any(
            isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "BatchNorm1d"
            for sub in ast.walk(encoder) if isinstance(sub, ast.Call)
        )
    check("encoder uses BatchNorm layers", encoder_has_batchnorm)

    module = find_class(model_tree, "AnnotateXModule")
    check("AnnotateXModule class exists", module is not None)
    mod_init = find_method(module, "__init__") if module else None
    check("module hidden_dim defaults to 128",
          mod_init is not None and default_of(mod_init, "hidden_dim") == 128)
    check("module mc_samples defaults to 20",
          mod_init is not None and default_of(mod_init, "mc_samples") == 20)

    opt_method = find_method(module, "configure_optimizers") if module else None
    calls = []
    if opt_method:
        for node in ast.walk(opt_method):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    check("optimizer is AdamW", "AdamW" in calls)
    check("scheduler is ReduceLROnPlateau", "ReduceLROnPlateau" in calls)
    lr_monitor = None
    if opt_method:
        for node in ast.walk(opt_method):
            # the contract is lr_scheduler.monitor == "val/loss" (dict key in the return)
            if isinstance(node, ast.Constant) and node.value == "val/loss":
                lr_monitor = node.value
    check("lr scheduler contract monitors val/loss", lr_monitor == "val/loss",
          f"got {lr_monitor!r}")

    mc_method = find_method(module, "predict_with_confidence") if module else None
    has_mc_loop = False
    if mc_method:
        for node in ast.walk(mc_method):
            if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) \
                    and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                has_mc_loop = True
    check("predict_with_confidence loops MC samples", has_mc_loop)

    metric_calls = {}
    if mod_init:
        for node in ast.walk(mod_init):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                metric_calls[node.func.id] = node
    go_f1 = metric_calls.get("MultilabelF1Score")
    macro = any(isinstance(k, ast.keyword) and k.arg == "average"
                 and isinstance(k.value, ast.Constant) and k.value.value == "macro"
                 for k in go_f1.keywords) if go_f1 else False
    check("metrics: BinaryAccuracy, BinaryF1Score, MultilabelF1Score(macro)",
          "BinaryAccuracy" in metric_calls and "BinaryF1Score" in metric_calls
          and go_f1 is not None and macro)

    gen_tree = parse("annotatex/data/generator.py")
    go_terms = None
    for node in gen_tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "GO_TERMS" for t in node.targets):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                go_terms = [e.value for e in node.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    check("GO_TERMS defines exactly 10 labels",
          go_terms is not None and len(go_terms) == 10 and len(set(go_terms)) == 10,
          f"got {len(go_terms) if go_terms is not None else None}")

    train_tree = parse("train.py")
    train_call_names = set()
    for n in ast.walk(train_tree):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                train_call_names.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                train_call_names.add(n.func.attr)
    check("train.py registers EarlyStopping", "EarlyStopping" in train_call_names)
    check("train.py registers ModelCheckpoint", "ModelCheckpoint" in train_call_names)
    early = next((n for n in ast.walk(train_tree)
                  if isinstance(n, ast.Call)
                  and ((isinstance(n.func, ast.Name) and n.func.id == "EarlyStopping")
                       or (isinstance(n.func, ast.Attribute) and n.func.attr == "EarlyStopping"))),
                 None)
    early_monitor = None
    early_patience = None
    if early:
        for kw in early.keywords:
            if kw.arg == "monitor" and isinstance(kw.value, ast.Constant):
                early_monitor = kw.value.value
            if kw.arg == "patience" and isinstance(kw.value, ast.Constant):
                early_patience = kw.value.value
    check("early stopping monitors val loss with patience 5",
          early_monitor == "val/loss" and early_patience == 5,
          f"got monitor={early_monitor!r} patience={early_patience!r}")
    train_constants = [n.value for n in ast.walk(train_tree)
                       if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    check("best checkpoint copied to annotatex-best.ckpt",
          "annotatex-best.ckpt" in train_constants)

    print()
    if FAILURES:
        print(f"verify_model_contract: FAILED ({len(FAILURES)} check(s))")
        return 1
    print("verify_model_contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
