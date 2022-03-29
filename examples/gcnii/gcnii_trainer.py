# !/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@File    :   gcnii_trainer.py
@Time    :   2021/12/22 16:12:02
@Author  :   Han Hui
'''

import os
import sys
# os.environ["CUDA_VISIBLE_DEVICES"] = "3"
sys.path.insert(0, os.path.abspath('../')) # adds path2gammagl to execute in command line.
import time
import numpy as np
import tensorlayerx as tlx
import tensorflow as tf
from gammagl.datasets import Cora
from gammagl.models import GCNIIModel, GCNModel
from gammagl.utils.config import Config
# from tensorlayerx.model import TrainOneStep, WithLoss

# parameters setting
n_epoch = 1000
learning_rate = 0.01
hidden_dim = 64
keep_rate = 0.4
l2_norm = 5e-4
alpha = 0.1
beta = 0.5
lambd = 0.5
num_layers = 64
variant = True

cora_path = r'../gammagl/datasets/raw_file/cora/'
best_model_path = r'./best_models/'

# physical_gpus = tf.config.experimental.list_physical_devices('GPU')
# if len(physical_gpus) > 0:
#     # dynamic allocate gpu memory
#     tf.config.experimental.set_memory_growth(physical_gpus[0], True)



# load dataset
dataset = Cora(cora_path)
graph, idx_train, idx_val, idx_test = dataset.process()
graph.add_self_loop(n_loops=1) # selfloop trick
edge_weight = GCNModel.calc_gcn_norm(graph.edge_index, graph.num_nodes)
edge_index = tlx.ops.convert_to_tensor(graph.edge_index)
x = tlx.ops.convert_to_tensor(graph.node_feat)
node_label = tlx.ops.convert_to_tensor(graph.node_label)
idx_train = tlx.ops.convert_to_tensor(idx_train)
idx_test = tlx.ops.convert_to_tensor(idx_test)
idx_val = tlx.ops.convert_to_tensor(idx_val)


# configurate and build model
cfg = Config(feature_dim=dataset.feature_dim,
             hidden_dim=hidden_dim,
             num_class=dataset.num_class,
             alpha = alpha,
             beta = beta,
             lambd = lambd,
             variant = variant,
             num_layers = num_layers,
             keep_rate=keep_rate,)
model = GCNIIModel(cfg, name="GCN")
train_weights = model.trainable_weights
optimizer = tlx.optimizers.Adam(learning_rate)
best_val_acc = 0.


# fit the training set
print('training starts')
start_time = time.time()

for epoch in range(n_epoch):
    # forward and optimize
    model.set_train()
    with tf.GradientTape() as tape:
        logits = model(x, edge_index, edge_weight, graph.num_nodes)
        train_logits = tlx.gather(logits, idx_train)
        train_labels = tlx.gather(node_label, idx_train)
        train_loss = tlx.losses.softmax_cross_entropy_with_logits(train_logits, train_labels)
        l2_loss = tf.add_n([tf.nn.l2_loss(v) for v in tape.watched_variables()]) * l2_norm
        # l2_loss = tf.nn.l2_loss(tape.watched_variables()[0]) * l2_norm  # Only perform normalization on first convolution.
        loss = train_loss + l2_loss
    grad = tape.gradient(loss, train_weights)
    optimizer.apply_gradients(zip(grad, train_weights))
    train_acc = np.mean(np.equal(np.argmax(train_logits, 1), train_labels))
    log_info = "epoch [{:0>3d}]  train loss: {:.4f}, l2_loss: {:.4f}, total_loss: {:.4f}, train acc: {:.4f}".format(epoch+1, train_loss, l2_loss, loss, train_acc)

    # evaluate
    model.set_eval()  # disable dropout
    logits = model(x, edge_index, edge_weight, graph.num_nodes)
    val_logits = tlx.gather(logits, idx_val)
    val_labels = tlx.gather(node_label, idx_val)
    val_loss = tlx.losses.softmax_cross_entropy_with_logits(val_logits, val_labels)
    val_acc = np.mean(np.equal(np.argmax(val_logits, 1), val_labels))
    log_info += ",  eval loss: {:.4f}, eval acc: {:.4f}".format(val_loss, val_acc)

    # save best model on evaluation set
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        model.save_weights(best_model_path+model.name+".npz")

    # # test when training
    # logits = model(x, sparse_adj)
    # test_logits = tlx.gather(logits, idx_test)
    # test_labels = tlx.gather(node_label, idx_test)
    # test_loss = tlx.losses.softmax_cross_entropy_with_logits(test_logits, test_labels)
    # test_acc = np.mean(np.equal(np.argmax(test_logits, 1), test_labels))
    # log_info += ",  test loss: {:.4f}, test acc: {:.4f}".format(test_loss, test_acc)

    print(log_info)

end_time = time.time()
print("training ends in {t}s".format(t=int(end_time-start_time)))

# test performance
model.load_weights(best_model_path+model.name+".npz")
model.set_eval()
logits = model(x, edge_index, edge_weight, graph.num_nodes)
test_logits = tlx.gather(logits, idx_test)
test_labels = tlx.gather(node_label, idx_test)
test_loss = tlx.losses.softmax_cross_entropy_with_logits(test_logits, test_labels)
test_acc = np.mean(np.equal(np.argmax(test_logits, 1), test_labels))
print("\ntest loss: {:.4f}, test acc: {:.4f}".format(test_loss, test_acc))



# class NetWithLoss(WithLoss):
#     def __init__(self, net, loss_fn):
#         super(NetWithLoss, self).__init__(backbone=net, loss_fn=loss_fn)
#
#     def forward(self, data, label):
#         logits = tlx.gather(
#             self._backbone(data['x'], data['edge_index'], data['edge_weight'], data['num_nodes']),
#             data['idx_train']
#         )
#         label = tlx.gather(label, data['idx_train'])
#         loss = self._loss_fn(logits, label)
#         return loss
#
#
# class GCNTrainOneStep(TrainOneStep):
#     def __init__(self, net_with_loss, optimizer, train_weights):
#         super().__init__(net_with_loss, optimizer, train_weights)
#         self.train_weights = train_weights
#
#     def __call__(self, data, label):
#         loss = self.net_with_train(data, label)
#         return loss
#
# loss = tlx.losses.softmax_cross_entropy_with_logits
# # metrics = tlx.metric.Accuracy() # zhen sb
# net = GCNIIModel(cfg, name="GCNII")
# train_weights = net.trainable_weights
# optimizer = tlx.optimizers.Adam(learning_rate)
# best_val_acc = 0.
#
# net_with_loss = NetWithLoss(net, loss)
# train_one_step = GCNTrainOneStep(net_with_loss, optimizer, train_weights)
#
# data = {
#     "x": x,
#     "edge_index": edge_index,
#     "edge_weight": edge_weight,
#     "idx_train": idx_train,
#     "idx_test": idx_test,
#     "idx_val": idx_val,
#     "num_nodes":graph.num_nodes,
# }
#
# # fit the training set
# print('training starts')
# for epoch in range(n_epoch):
#     start_time = time.time()
#     net.set_train()
#     # train one step
#     train_loss = train_one_step(data, node_label)
#     # eval
#     _logits = net(data['x'], data['edge_index'], data['edge_weight'], data['num_nodes'])
#
#     train_logits = tlx.gather(_logits, data['idx_train'])
#     train_label = tlx.gather(node_label, data['idx_train'])
#     train_acc = np.mean(np.equal(np.argmax(train_logits, 1), train_label))
#
#     val_logits = tlx.gather(_logits, data['idx_val'])
#     val_label = tlx.gather(node_label, data['idx_val'])
#     val_acc = np.mean(np.equal(np.argmax(val_logits, 1), val_label))
#
#     print("Epoch [{:0>3d}]  ".format(epoch + 1)\
#           + "   train loss: {:.4f}".format(train_loss)\
#           + "   train acc: {:.4f}".format(train_acc)\
#           + "   val acc: {:.4f}".format(val_acc))
#
#     # save best model on evaluation set
#     if val_acc > best_val_acc:
#         best_val_acc = val_acc
#         net.save_weights(best_model_path+net.name+".npz", format='npz_dict')
#
# net.load_weights(best_model_path+net.name+".npz", format='npz_dict')
# test_logits = tlx.gather(net(data['x'], data['edge_index'], data['edge_weight'], data['num_nodes']), data['idx_test'])
# test_label = tlx.gather(node_label, data['idx_test'])
# test_acc = np.mean(np.equal(np.argmax(test_logits, 1), test_label))
# print("Test acc:  {:.4f}".format(test_acc))
