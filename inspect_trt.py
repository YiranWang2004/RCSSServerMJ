import argparse
import sys


def inspect_trt(path: str):
    try:
        import tensorrt as trt
    except ImportError:
        print("错误: 未找到 tensorrt 模块，请先安装 TensorRT Python 包。")
        print("  pip install tensorrt")
        sys.exit(1)

    TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(TRT_LOGGER)

    with open(path, "rb") as f:
        engine_data = f.read()

    engine = runtime.deserialize_cuda_engine(engine_data)
    if engine is None:
        print(f"错误: 无法加载 TRT 文件: {path}")
        sys.exit(1)

    print(f"文件: {path}")
    print(f"TensorRT 版本: {trt.__version__}")
    print(f"最大 batch size: {engine.max_batch_size}")

    # TensorRT >= 8.5 使用 get_tensor_name / get_tensor_shape 接口
    # TensorRT <  8.5 使用 binding 接口
    trt_version = tuple(int(x) for x in trt.__version__.split(".")[:2])

    print(f"\n=== Bindings ({engine.num_bindings} 个) ===")
    inputs = []
    outputs = []
    for i in range(engine.num_bindings):
        name = engine.get_binding_name(i)
        shape = list(engine.get_binding_shape(i))
        dtype = engine.get_binding_dtype(i)
        is_input = engine.binding_is_input(i)
        kind = "输入" if is_input else "输出"
        print(f"  [{i}] {kind}  name={name}  shape={shape}  dtype={dtype}")
        if is_input:
            inputs.append((name, shape, dtype))
        else:
            outputs.append((name, shape, dtype))

    print("\n=== 汇总 ===")
    print("  输入:")
    for name, shape, dtype in inputs:
        print(f"    {name}: shape={shape}, dtype={dtype}")
    print("  输出:")
    for name, shape, dtype in outputs:
        print(f"    {name}: shape={shape}, dtype={dtype}")

    # 动态 shape 支持检测
    print("\n=== 动态 Shape 配置 ===")
    num_profiles = engine.num_optimization_profiles
    print(f"  优化配置数量 (optimization profiles): {num_profiles}")
    for p in range(num_profiles):
        print(f"\n  Profile {p}:")
        for i in range(engine.num_bindings // num_profiles):
            binding_idx = p * (engine.num_bindings // num_profiles) + i
            name = engine.get_binding_name(binding_idx)
            if engine.binding_is_input(binding_idx):
                min_shape = engine.get_profile_shape(p, name)[0]
                opt_shape = engine.get_profile_shape(p, name)[1]
                max_shape = engine.get_profile_shape(p, name)[2]
                if min_shape != opt_shape or opt_shape != max_shape:
                    print(f"    {name}: min={list(min_shape)}  opt={list(opt_shape)}  max={list(max_shape)}")
                else:
                    print(f"    {name}: 静态 shape={list(opt_shape)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查看 TensorRT Engine (.trt/.engine) 网络结构")
    parser.add_argument("trt_path", help="TRT 文件路径")
    args = parser.parse_args()
    inspect_trt(args.trt_path)
