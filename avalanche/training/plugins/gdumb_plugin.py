#!/usr/bin/env python
# -*- coding: utf-8 -*-

################################################################################
# Copyright (c) 2020 ContinualAI Research                                      #
# Copyrights licensed under the CC BY 4.0 License.                             #
# See the accompanying LICENSE file for terms.                                 #
#                                                                              #
# Date: 1-06-2020                                                              #
# Author(s): Andrea Cossu                                                #
# E-mail: contact@continualai.org                                              #
# Website: clair.continualai.org                                               #
################################################################################

from __future__ import absolute_import
from __future__ import division
# Python 2-3 compatible
from __future__ import print_function

import torch
from torch.utils.data import TensorDataset

from avalanche.training.skeletons import TrainingFlow
from avalanche.training.skeletons import StrategySkeleton
from collections import defaultdict


class GDumbPlugin(StrategySkeleton):
    """
    A GDumb plugin. At each step the model
    is trained with all and only the data of the external memory.
    The memory is updated at the end of each step to add new classes or
    new examples of already encountered classes.


    This plugin can be combined with a Naive strategy to obtain the 
    standard GDumb strategy.

    https://www.robots.ox.ac.uk/~tvg/publications/2020/gdumb.pdf
    """

    def __init__(self, mem_size=200):

        super().__init__()

        self.mem_size = mem_size
        self.ext_mem = None
        self.counter = defaultdict(int) # count occurrences for each class

    @TrainingFlow
    def adapt_train_dataset(self, step_id, train_dataset):
        """ Before training we make sure to organize the memory following
            GDumb approach and updating the dataset accordingly.
        """

        # helper memory to store new patterns when memory is not full
        # this is necessary since it is not possible to concatenate
        # patterns into an existing TensorDataset 
        # (dataset.tensors[0] does not support item assignment)
        ext_mem = [[], []]

        # for each pattern, add it to the memory or not
        for i, (pattern, target) in enumerate(train_dataset):
            target_value = target.item()
            
            if self.counter == {}:
                patterns_per_class = 1 # any positive (>0) number is ok
            else:
                patterns_per_class = int(
                    self.mem_size / len(self.counter.keys())
                    )

            if target_value not in self.counter or \
               self.counter[target_value] < patterns_per_class:
                    # full memory, remove item from most represented class
                    if sum(self.counter.values()) >= self.mem_size: 
                        to_remove = max(self.counter, key=self.counter.get)
                        for j in range(len(self.ext_mem.tensors[1])):
                            if self.ext_mem.tensors[1][j].item() == to_remove:
                                self.ext_mem.tensors[0][j] = pattern
                                self.ext_mem.tensors[1][j] = target
                                break
                        self.counter[to_remove] -= 1

                    # memory not full, just add the new pattern
                    else:
                        ext_mem[0].append(pattern)
                        ext_mem[1].append(target.unsqueeze(0))
                    
                    self.counter[target_value] += 1

        # concatenate previous memory with newly added patterns.
        # when ext_mem[0] == [] the memory (self.ext_mem) is full and patterns 
        # are inserted into self.ext_mem directly
        if len(ext_mem[0]) > 0:
            memx = torch.cat(ext_mem[0], dim=0)
            memy = torch.cat(ext_mem[1], dim=0)            
            if self.ext_mem is None:
                self.ext_mem = TensorDataset(memx, memy)
            else:
                self.ext_mem = TensorDataset(
                        torch.cat( [memx, self.ext_mem.tensors[0]], dim=0),
                        torch.cat( [memy, self.ext_mem.tensors[1]], dim=0)
                )

        self.update_namespace(train_dataset=self.ext_mem)

__all__ = ['GDumbPlugin']