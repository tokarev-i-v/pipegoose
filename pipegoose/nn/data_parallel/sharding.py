from abc import ABC, abstractclassmethod

import torch
import torch.nn.functional as F
from torch import nn

from pipegoose.distributed.context import ParallelContext
from pipegoose.nn.data_parallel.utils import free_storage


class ShardingStategy(ABC):
    @abstractclassmethod
    def shard(self):
        raise NotImplementedError("")


class GreedySharding(ShardingStategy):
    def __init__(self, module: nn.Module, parallel_context: ParallelContext):
        self.module = module
        self.parallel_context = parallel_context

        # TODO: change
        self.params = []

    @torch.no_grad()
    def shard(self) -> torch.Tensor:
        world_size = self.parallel_context.get_world_size()

        for p in self.params:
            assert not hasattr(p, "_is_sharded")

            if world_size > 1:
                orig_data = p.data
                p.data = self._get_shard(p.data)
                p._is_sharded = True
                free_storage(orig_data)

    def _get_shard(self, data: torch.Tensor) -> torch.Tensor:
        world_size = self.parallel_context.get_world_size()
        rank = self.parallel_context.get_rank()

        chunks = list(data.flatten().chunk(world_size))

        while len(chunks) < world_size:
            chunks.append(torch.empty(0))

        shard = chunks[rank].clone()
        num_to_pad = chunks[0].numel() - shard.numel()
        if num_to_pad > 0:
            shard = F.pad(shard, [0, num_to_pad])
        return shard
