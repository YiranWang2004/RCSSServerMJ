import onnx
import numpy as np
import argparse


def inspect_onnx(path: str):
    model = onnx.load(path)
    graph = model.graph
    weights = {init.name: onnx.numpy_helper.to_array(init) for init in graph.initializer}

    print(f"文件: {path}")
    print(f"ONNX opset: {model.opset_import[0].version}")

    print("\n=== 输入 ===")
    for inp in graph.input:
        if inp.name in weights:
            continue
        shape = [d.dim_value for d in inp.type.tensor_type.shape.dim]
        dtype = inp.type.tensor_type.elem_type
        print(f"  {inp.name}: shape={shape}, dtype={dtype}")

    print("\n=== 输出 ===")
    for out in graph.output:
        shape = [d.dim_value for d in out.type.tensor_type.shape.dim]
        dtype = out.type.tensor_type.elem_type
        print(f"  {out.name}: shape={shape}, dtype={dtype}")

    print("\n=== 网络层结构 ===")
    for node in graph.node:
        inputs = [i for i in node.input if i not in weights and i != ""]
        params = [i for i in node.input if i in weights]
        param_shapes = [str(weights[p].shape) for p in params]
        print(f"  [{node.op_type}]  in={inputs}  params={list(zip(params, param_shapes))}  out={list(node.output)}")

    print("\n=== 权重参数 ===")
    total_params = 0
    for name, arr in weights.items():
        n = int(np.prod(arr.shape))
        total_params += n
        print(f"  {name}: shape={arr.shape}  ({n:,} params)")
    print(f"\n  总参数量: {total_params:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查看 ONNX 模型网络结构")
    parser.add_argument("onnx_path", help="ONNX 文件路径")
    args = parser.parse_args()
    inspect_onnx(args.onnx_path)
