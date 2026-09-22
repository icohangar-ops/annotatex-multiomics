"""Evidence-matrix tests — model contract (README Features confidence claims).

Checks the real AnnotateXModule: architecture defaults, MC-dropout confidence
head shapes and probability ranges, and the configure_optimizers contract.
"""
import torch
from annotatex.models.annotatex import AnnotateXModule


def test_module_default_architecture():
    module = AnnotateXModule()
    assert module.hparams["input_dim"] == 6
    assert module.hparams["hidden_dim"] == 128
    assert module.hparams["mc_samples"] == 20
    assert module.network.de_head.out_features == 1
    assert module.network.go_head.out_features == 10


def test_predict_with_confidence_shapes_and_ranges():
    module = AnnotateXModule()
    module.eval()
    torch.manual_seed(0)
    preds = module.predict_with_confidence(torch.zeros(4, 6))
    assert preds["de_prob"].shape == (4,)
    assert preds["go_probs"].shape == (4, 10)
    for key in ("de_prob", "de_confidence", "go_confidence"):
        assert torch.all(preds[key] >= 0.0), key
        assert torch.all(preds[key] <= 1.0), key


def test_configure_optimizers_contract():
    module = AnnotateXModule()
    out = module.configure_optimizers()
    assert isinstance(out, dict) and "optimizer" in out
    assert isinstance(out["optimizer"], torch.optim.AdamW)
    sched = out["lr_scheduler"]["scheduler"]
    assert isinstance(sched, torch.optim.lr_scheduler.ReduceLROnPlateau)
    assert out["lr_scheduler"]["monitor"] == "val/loss"
